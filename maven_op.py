from mcp.server.fastmcp import FastMCP
import logging
import logging.handlers
import sys
import os
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any, Union
import google.generativeai as genai
from google.generativeai import GenerativeModel
from dotenv import load_dotenv
from pydantic import BaseModel
from logger_config import setup_logging, get_logger, log_performance

# Setup logging
setup_logging(
    log_level=logging.DEBUG,
    log_file_path='logs/maven_op.log'
)
logger = get_logger(__name__)

class ProjectDetails(BaseModel):
    success: bool
    project_name: str
    jdk_version: Optional[str]
    spring_boot_version: Optional[str]
    all_jdk_versions: List[str]
    all_spring_boot_versions: List[str]

class ProjectAnalysis(BaseModel):
    success: bool
    projects: List[ProjectDetails]
    total_projects: int
    analyzed_projects: int

class MigrationPlanArgs(BaseModel):
    content: str
    
    @classmethod
    def from_args(cls, args: Union[str, List[str], Dict[str, Any]]) -> 'MigrationPlanArgs':
        """Create MigrationPlanArgs from various input formats."""
        if isinstance(args, str):
            return cls(content=args)
        elif isinstance(args, list) and len(args) > 0:
            return cls(content=args[0])
        elif isinstance(args, dict) and "content" in args:
            return cls(content=args["content"])
        else:
            raise ValueError("Invalid argument format")

# Load environment variables
load_dotenv()

# Initialize FastMCP
logger.info("Initializing Maven Operation MCP Server")
mcp = FastMCP("MavenOp")
logger.info("FastMCP instance created")

# Get PROJECTS_BASE_PATH from environment
PROJECTS_BASE_PATH = os.getenv('PROJECTS_BASE_PATH')
logger.info(f"Projects base path: {PROJECTS_BASE_PATH}")

@log_performance(logger)
def get_full_project_path(project_name: str) -> str:
    """Get the full project path from the project name."""
    if not PROJECTS_BASE_PATH:
        logger.error("PROJECTS_BASE_PATH environment variable not set")
        raise ValueError("PROJECTS_BASE_PATH environment variable not set")
    full_path = os.path.join(PROJECTS_BASE_PATH, project_name)
    logger.debug(f"Full project path: {full_path}")
    return full_path

@log_performance(logger)
def serialize_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize MCP response to ensure JSON compatibility."""
    try:
        logger.debug("Starting response serialization", extra={"raw_response": str(response)})
        serialized = {}
        for key, value in response.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                serialized[key] = value
            elif isinstance(value, list):
                serialized[key] = [
                    str(item) if not isinstance(item, (str, int, float, bool, type(None)))
                    else item
                    for item in value
                ]
            else:
                serialized[key] = str(value)
        logger.debug("Response serialization completed", extra={"serialized": serialized})
        return serialized
    except Exception as e:
        logger.error("Response serialization failed", extra={"error": str(e)}, exc_info=True)
        return {"success": False, "error": "Response serialization failed"}

@log_performance(logger)
def find_pom_files(project_path: str) -> List[str]:
    """Find all pom.xml files in the project directory."""
    logger.info(f"Starting pom.xml search in: {project_path}")
    pom_files = []
    try:
        for root, dirs, files in os.walk(project_path):
            logger.debug(f"Scanning directory: {root}")
            if "pom.xml" in files:
                pom_path = os.path.join(root, "pom.xml")
                pom_files.append(pom_path)
                logger.debug(f"Found pom.xml", extra={"path": pom_path})
        
        logger.info("pom.xml search completed", 
                   extra={"total_files": len(pom_files), "files": pom_files})
        return pom_files
    except Exception as e:
        logger.error("Error during pom.xml search", 
                    extra={"project_path": project_path, "error": str(e)},
                    exc_info=True)
        return []

@log_performance(logger)
def extract_jdk_version(pom_path: str) -> Optional[str]:
    """Extract JDK version from a pom.xml file."""
    logger.info(f"Extracting JDK version", extra={"pom_path": pom_path})
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}
        logger.debug("Successfully parsed pom.xml")

        # Check various locations for Java version
        locations = [
            ".//mvn:properties/mvn:java.version",
            ".//mvn:properties/mvn:maven.compiler.source",
            ".//mvn:build/mvn:plugins//mvn:configuration/mvn:source",
        ]

        for xpath in locations:
            logger.debug(f"Checking xpath location", extra={"xpath": xpath})
            version_elem = root.find(xpath, ns)
            if version_elem is not None and version_elem.text:
                version = version_elem.text
                logger.info("JDK version found", 
                           extra={"version": version, "xpath": xpath})
                return version

        logger.warning("No JDK version found", extra={"pom_path": pom_path})
        return None
    except Exception as e:
        logger.error("Error extracting JDK version", 
                    extra={"pom_path": pom_path, "error": str(e)},
                    exc_info=True)
        return None

@log_performance(logger)
def extract_spring_boot_version(pom_path: str) -> Optional[str]:
    """Extract Spring Boot version from a pom.xml file."""
    logger.info(f"Extracting Spring Boot version", extra={"pom_path": pom_path})
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}
        logger.debug("Successfully parsed pom.xml")

        # Check parent version first
        parent = root.find(".//mvn:parent", ns)
        if parent is not None:
            group_id = parent.find("mvn:groupId", ns)
            artifact_id = parent.find("mvn:artifactId", ns)
            version = parent.find("mvn:version", ns)
            
            if (group_id is not None and group_id.text == "org.springframework.boot" and 
                artifact_id is not None and artifact_id.text == "spring-boot-starter-parent" and
                version is not None):
                logger.info("Spring Boot version found in parent", 
                           extra={"version": version.text})
                return version.text

        # Check dependencies
        logger.debug("Checking dependencies for Spring Boot version")
        dependencies = root.findall(".//mvn:dependencies/mvn:dependency", ns)
        for dep in dependencies:
            group_id = dep.find("mvn:groupId", ns)
            artifact_id = dep.find("mvn:artifactId", ns)
            version = dep.find("mvn:version", ns)
            
            if (group_id is not None and group_id.text == "org.springframework.boot" and
                artifact_id is not None and "spring-boot" in artifact_id.text and
                version is not None):
                logger.info("Spring Boot version found in dependencies", 
                           extra={"version": version.text})
                return version.text

        logger.warning("No Spring Boot version found", extra={"pom_path": pom_path})
        return None
    except Exception as e:
        logger.error("Error extracting Spring Boot version", 
                    extra={"pom_path": pom_path, "error": str(e)},
                    exc_info=True)
        return None

def analyze_project_impl(project_name: str) -> Dict[str, Any]:
    """
    Analyze a Maven project to identify JDK and Spring Boot versions.
    
    Args:
        project_name: Name of the Maven project
        
    Returns:
        Dict containing analysis results with JDK and Spring Boot versions
    """
    logger.info(f"Starting project analysis for: {project_name}")
    
    try:
        project_path = get_full_project_path(project_name)
        if not os.path.exists(project_path):
            logger.error(f"Project path does not exist: {project_path}")
            return {"success": False, "error": "Project path does not exist"}

        pom_files = find_pom_files(project_path)
        if not pom_files:
            logger.error("No pom.xml files found")
            return {"success": False, "error": "No pom.xml files found in the project"}

        # Extract versions from all pom files
        jdk_versions = set()
        spring_boot_versions = set()
        
        for pom_file in pom_files:
            logger.debug(f"Processing pom file: {pom_file}")
            
            # Get JDK version
            jdk_version = extract_jdk_version(pom_file)
            if jdk_version:
                jdk_versions.add(jdk_version)
                logger.debug(f"Added JDK version {jdk_version} to versions set")
            
            # Get Spring Boot version
            spring_version = extract_spring_boot_version(pom_file)
            if spring_version:
                spring_boot_versions.add(spring_version)
                logger.debug(f"Added Spring Boot version {spring_version} to versions set")

        # Prepare response
        response = {"success": True}
        
        # Add JDK version if found
        if jdk_versions:
            min_jdk = min(jdk_versions)
            response["jdk_version"] = min_jdk
            logger.info(f"Selected JDK version: {min_jdk}")
        else:
            logger.warning("No JDK versions found")
            response["jdk_version"] = None

        # Add Spring Boot version if found
        if spring_boot_versions:
            min_spring = min(spring_boot_versions)
            response["spring_boot_version"] = min_spring
            logger.info(f"Selected Spring Boot version: {min_spring}")
        else:
            logger.warning("No Spring Boot versions found")
            response["spring_boot_version"] = None

        # Add all found versions for reference
        response["all_jdk_versions"] = list(jdk_versions)
        response["all_spring_boot_versions"] = list(spring_boot_versions)
        
        logger.info("Analysis complete")
        return response
        
    except Exception as e:
        logger.error("Error during project analysis", exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool(name="analyzeProject", description="Analyze a Maven project to identify JDK version")
def analyze_project() -> dict:
    """
    Analyze a Maven project to identify JDK version.
    Reads the project name from PROJECTS_BASE_PATH directory.
    """
    try:
        logger.info("=== Starting analyzeProject ===")
        
        if not PROJECTS_BASE_PATH:
            logger.error("PROJECTS_BASE_PATH environment variable not set")
            return {"success": False, "error": "PROJECTS_BASE_PATH environment variable not set"}
            
        if not os.path.exists(PROJECTS_BASE_PATH):
            logger.error(f"Projects base path does not exist: {PROJECTS_BASE_PATH}")
            return {"success": False, "error": f"Projects base path does not exist: {PROJECTS_BASE_PATH}"}
            
        # Get list of directories in PROJECTS_BASE_PATH
        try:
            projects = [d for d in os.listdir(PROJECTS_BASE_PATH) 
                       if os.path.isdir(os.path.join(PROJECTS_BASE_PATH, d))]
        except Exception as e:
            logger.error(f"Error reading projects directory: {e}", exc_info=True)
            return {"success": False, "error": f"Error reading projects directory: {str(e)}"}
            
        if not projects:
            logger.error("No projects found in projects directory")
            return {"success": False, "error": "No projects found in projects directory"}
            
        logger.info(f"Found projects: {projects}")
        
        # Analyze each project
        results = []
        for project_name in projects:
            logger.info(f"Analyzing project: {project_name}")
            result = analyze_project_impl(project_name)
            if result.get("success", False):
                result["project_name"] = project_name
                results.append(result)
            else:
                logger.warning(f"Failed to analyze project {project_name}: {result.get('error', 'Unknown error')}")
        
        if not results:
            logger.error("No projects could be successfully analyzed")
            return {"success": False, "error": "No projects could be successfully analyzed"}
            
        # Combine results
        combined_result = {
            "success": True,
            "projects": results,
            "total_projects": len(projects),
            "analyzed_projects": len(results)
        }
        
        serialized = serialize_response(combined_result)
        logger.debug(f"Analysis results after serialization: {serialized}")
        
        logger.info("=== Completed analyzeProject ===")
        return serialized
        
    except Exception as e:
        logger.error("Error in analyzeProject", exc_info=True)
        return {"success": False, "error": str(e)}

def get_latest_java_version(llm: GenerativeModel) -> str:
    """Use Gemini LLM to identify the latest stable Java version."""
    logger.debug("Requesting latest Java version from LLM")
    try:
        prompt = """What is the latest stable version of Java/JDK available for production use?
        Respond with ONLY the version number (e.g., '21' for Java 21), nothing else."""
        
        logger.debug(f"Sending prompt to LLM: {prompt}")
        response = llm.generate_content(prompt)
        latest_version = response.text.strip()
        logger.info(f"LLM identified latest Java version: {latest_version}")
        return latest_version
    except Exception as e:
        logger.error("Error getting latest Java version from LLM", exc_info=True)
        logger.info("Falling back to default version: 21")
        return "21"

def get_latest_spring_boot_version(llm: GenerativeModel) -> str:
    """Use Gemini LLM to identify the latest stable Spring Boot version."""
    logger.debug("Requesting latest Spring Boot version from LLM")
    try:
        prompt = """What is the latest stable version of Spring Boot available for production use? Check the latest version from https://start.spring.io/
        Respond with ONLY the version number (e.g., '3.2.1'), nothing else."""
        
        logger.debug(f"Sending prompt to LLM: {prompt}")
        response = llm.generate_content(prompt)
        latest_version = response.text.strip()
        logger.info(f"LLM identified latest Spring Boot version: {latest_version}")
        return latest_version
    except Exception as e:
        logger.error("Error getting latest Spring Boot version from LLM", exc_info=True)
        logger.info("Falling back to default version: 3.2.1")
        return "3.2.1"

def score_recipe_match(recipe: Dict, target_version: str, llm: GenerativeModel) -> float:
    """Use LLM to score how well a recipe matches the migration goal."""
    logger.debug(f"Scoring recipe match for Spring Boot {target_version}")
    logger.debug(f"Recipe being scored: {recipe['name']}")
    
    try:
        prompt = f"""As a Java and Spring Boot migration expert, score how well this recipe matches the migration goal.
        
        Migration Goal: {'Migrate to Spring Boot'} {target_version}
        
        Recipe:
        {json.dumps(recipe, indent=2)}
        
        Respond with EXACTLY a number between 0 and 100, where:
        - 100 means perfect match (exact match for Spring Boot {target_version} migration)
        - 75+ means very relevant (mentions Spring Boot upgrade to similar version)
        - 50+ means somewhat relevant (mentions Spring Boot but different version)
        - 25+ means slightly relevant (mentions upgrades but not specific to Spring Boot)
        - 0 means not relevant at all"""

        logger.debug(f"Sending scoring prompt to LLM")
        response = llm.generate_content(prompt)
        score = float(response.text.strip())
        logger.info(f"Recipe '{recipe['name']}' received score: {score}")
        return min(max(score, 0), 100)
    except Exception as e:
        logger.error(f"Error scoring recipe '{recipe['name']}'", exc_info=True)
        return 0

def find_best_recipe(recipes: List[Dict], target_version: str, llm: GenerativeModel) -> Optional[Dict]:
    """Find the best matching recipe for the target version."""
    logger.info(f"Finding best recipe for Spring Boot {target_version}")
    
    # First try exact match
    search_pattern = f"migrate to spring boot {target_version}"
    logger.debug(f"Searching for exact pattern: {search_pattern}")
    
    exact_matches = [
        recipe for recipe in recipes
        if search_pattern.lower() in recipe["name"].lower()
    ]
    logger.debug(f"Found {len(exact_matches)} exact matches")

    if exact_matches:
        match = exact_matches[0]
        logger.info(f"Using exact match: {match['name']}")
        return {
            "recipe_id": match["id"],
            "recipe_name": match["name"],
            "recipe_description": match.get("description", ""),
            "match_type": "exact"
        }

    # If no exact match, try substring match for version (e.g., 3.3 for 3.3.0)
    logger.info("No exact match found, trying version substring matches")
    version_parts = target_version.split('.')
    version_patterns = []
    
    # Generate version patterns (e.g., for 3.3.0 -> ["3.3.0", "3.3"])
    for i in range(len(version_parts), 0, -1):
        version_pattern = '.'.join(version_parts[:i])
        version_patterns.append(version_pattern)
    
    logger.debug(f"Generated version patterns: {version_patterns}")
    
    # Filter recipes that contain "migrate to spring boot" and any version pattern
    filtered_recipes = []
    for recipe in recipes:
        recipe_name_lower = recipe["name"].lower()
        if "migrate to spring boot" in recipe_name_lower:
            for pattern in version_patterns:
                if pattern in recipe_name_lower:
                    filtered_recipes.append(recipe)
                    break

    logger.info(f"Found {len(filtered_recipes)} recipes matching version patterns")

    # If we have filtered recipes, score them
    if filtered_recipes:
        logger.info("Scoring filtered recipes")
        scored_recipes = []
        for recipe in filtered_recipes:
            logger.debug(f"Scoring recipe: {recipe['name']}")
            score = score_recipe_match(recipe, target_version, llm)
            scored_recipes.append((recipe, score))

        scored_recipes.sort(key=lambda x: x[1], reverse=True)
        logger.debug("Recipes sorted by score")
        
        if scored_recipes and scored_recipes[0][1] > 70:
            best_match = scored_recipes[0][0]
            score = scored_recipes[0][1]
            logger.info(f"Selected best match: {best_match['name']} (score: {score})")
            return {
                "recipe_id": best_match["id"],
                "recipe_name": best_match["name"],
                "recipe_description": best_match.get("description", ""),
                "match_type": "scored",
                "match_score": score
            }
    
    logger.info("No suitable matches found")
    return None

@mcp.tool(name="migrationPlan", description="Generate migration plan based on Spring Boot version")
def migration_plan() -> dict:
    """
    Generate migration plan based on Spring Boot version.
    
    Args:
        args: Spring Boot version as string, list, or dictionary with content field
    """
    try:
        logger.info("=== Starting migrationPlan ===")
            
        # Initialize Gemini
        load_dotenv()
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not found in environment variables")
            return {"success": False, "error": "GEMINI_API_KEY not found"}
            
        genai.configure(api_key=GEMINI_API_KEY)
        llm = GenerativeModel("gemini-2.0-flash")
        logger.debug("Gemini LLM initialized successfully")

        # Get latest Spring Boot version
        latest_spring = get_latest_spring_boot_version(llm)
        logger.info(f"Latest stable version of Spring Boot: {latest_spring}")
        
        # Load Moderne recipes
        try:
            with open("C:\\Users\\rajap\\moderne_recipes.json", 'r') as f:
                recipes = json.load(f)
            logger.debug(f"Loaded {len(recipes)} recipes")
        except Exception as e:
            logger.error("Failed to load recipes file", exc_info=True)
            return {"success": False, "error": f"Could not load recipes: {str(e)}"}
            
        # Determine if updates are needed
            
        logger.info(f"Finding Spring Boot migration recipe for version {latest_spring}")
        recipe_match = find_best_recipe(recipes, latest_spring, llm)
        if recipe_match:
            result = {
                "success": True,
                "target_version": latest_spring,
                "recipe": recipe_match
            }
        else:
            result = {
                "success": False,
                "error": f"No suitable migration recipe found for Spring Boot {latest_spring}"
            }
        
        logger.debug(f"Migration plan results: {result}")
        logger.info("=== Completed migrationPlan ===")
        return result
        
    except Exception as e:
        logger.error("Error in migrationPlan", exc_info=True)
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    try:
        # Verify environment
        if not PROJECTS_BASE_PATH:
            logger.error("PROJECTS_BASE_PATH environment variable not set")
            sys.exit(1)
            
        # Start the MCP server with stdio transport
        logger.info("Starting Maven Operation MCP server with stdio transport")
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        mcp.run(transport="stdio")
        
    except Exception as e:
        logger.error(f"Error starting Maven Operation MCP server: {e}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0) 