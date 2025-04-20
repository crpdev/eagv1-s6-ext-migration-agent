import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from models import UserPreferences, MigrationStrategy, TargetVersion
from cognitive.perception import PerceptionLayer
from cognitive.memory import MemoryLayer
from cognitive.decision_making import DecisionMakingLayer
from cognitive.action import ActionLayer
from logger_config import setup_logging

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(
    log_level="INFO",
    log_file=f"logs/java_migration_client_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
logger = logging.getLogger(__name__)

class JavaMigrationClient:
    def __init__(self):
        self.memory = MemoryLayer()
        self.moderne_session = None
        self.maven_session = None
        self.perception = None
        self.decision_making = None
        self.action = None
        
    async def initialize(self):
        """
        Initialize the migration client and establish server connections.
        """
        try:
            logger.info("Initializing Java Migration Client")
            
            # Create server connections
            moderne_server_params = StdioServerParameters(
                command="python",
                args=["moderne_mcp_server.py"]
            )
            
            maven_server_params = StdioServerParameters(
                command="python",
                args=["maven_op.py"]
            )
            
            # Establish connections
            moderne_read, moderne_write = await stdio_client(moderne_server_params).__aenter__()
            maven_read, maven_write = await stdio_client(maven_server_params).__aenter__()
            
            # Create sessions
            self.moderne_session = await ClientSession(moderne_read, moderne_write).__aenter__()
            self.maven_session = await ClientSession(maven_read, maven_write).__aenter__()
            
            # Initialize sessions
            await self.moderne_session.initialize()
            await self.maven_session.initialize()
            
            # Initialize cognitive layers
            self.perception = PerceptionLayer(self.moderne_session, self.maven_session)
            self.decision_making = DecisionMakingLayer(self.moderne_session, self.maven_session)
            self.action = ActionLayer(self.moderne_session, self.maven_session)
            
            logger.info("Java Migration Client initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Java Migration Client: {str(e)}")
            raise
            
    async def set_preferences(
        self,
        project_directory: str,
        migration_strategy: MigrationStrategy,
        target_version: TargetVersion
    ) -> None:
        """
        Set user preferences for the migration process.
        """
        try:
            preferences = UserPreferences(
                project_directory=project_directory,
                migration_strategy=migration_strategy,
                target_version=target_version
            )
            
            self.memory.initialize_state(preferences)
            logger.info("User preferences set successfully", 
                       extra_data={"preferences": preferences.dict()})
            
        except Exception as e:
            logger.error(f"Error setting preferences: {str(e)}")
            raise
            
    async def run_migration(self) -> bool:
        """
        Run the complete migration process.
        """
        try:
            if not self.memory.state:
                logger.error("Cannot run migration: State not initialized")
                return False
                
            # 1. Perception: Analyze the project
            analysis = await self.perception.analyze_project(self.memory.state.preferences)
            if not analysis:
                return False
                
            self.memory.update_project_analysis(analysis)
            
            # 2. Decision Making: Create migration plan
            plan = await self.decision_making.create_migration_plan(
                analysis,
                self.memory.state.preferences.migration_strategy,
                self.memory.state.preferences.target_version
            )
            if not plan:
                return False
                
            self.memory.update_migration_plan(plan)
            
            # 3. Action: Execute migration steps
            for step_index in range(len(plan.required_steps)):
                success = await self.action.execute_migration_step(plan, step_index)
                if not success:
                    return False
                self.memory.increment_step()
                
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during migration: {str(e)}")
            return False
            
    async def close(self):
        """
        Clean up resources and close connections.
        """
        try:
            if self.moderne_session:
                await self.moderne_session.__aexit__(None, None, None)
            if self.maven_session:
                await self.maven_session.__aexit__(None, None, None)
            logger.info("Resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            
async def main():
    client = JavaMigrationClient()
    try:
        await client.initialize()
        
        # Example usage
        await client.set_preferences(
            project_directory=os.getenv("PROJECT_DIRECTORY", ""),
            migration_strategy=MigrationStrategy.SPRING_BOOT,
            target_version=TargetVersion.STABLE
        )
        
        success = await client.run_migration()
        if success:
            logger.info("Migration process completed successfully")
        else:
            logger.error("Migration process failed")
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        await client.close()
        
if __name__ == "__main__":
    asyncio.run(main()) 