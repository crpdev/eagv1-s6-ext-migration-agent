import logging
from typing import Optional, Dict, Any, Tuple, List
from pydantic import BaseModel
from models import ProjectAnalysis, UserPreferences
from logger_config import get_logger
from mcp import ClientSession
import xml.etree.ElementTree as ET
import os
from maven_op import (
    extract_jdk_version as maven_extract_jdk,
    extract_spring_boot_version as maven_extract_spring_boot,
    find_pom_files
)

logger = get_logger(__name__)

# Type aliases
SessionPair = Tuple[ClientSession, ClientSession]
ToolResult = Dict[str, Any]

class AnalysisData(BaseModel):
    """Raw analysis data from Maven tools"""
    content: str
    metadata: Dict[str, Any] = {}
    pom_files: List[str] = []

class PerceptionLayer:
    def __init__(self, moderne_session, maven_session):
        self.moderne_session = moderne_session
        self.maven_session = maven_session
        
    async def analyze_project(self, preferences: UserPreferences) -> Optional[ProjectAnalysis]:
        """
        Analyzes the project structure and dependencies.
        """
        try:
            logger.info("Starting project analysis", extra_data={"project_dir": preferences.project_directory})
            
            # Analyze project using Maven tools
            maven_analysis = await self.maven_session.call_tool("analyzeProject")
            
            if not maven_analysis:
                logger.error("Failed to analyze project with Maven tools")
                return None
                
            # Parse the analysis results
            analysis_data = maven_analysis.content[0].text
            
            # Extract project details
            project_analysis = ProjectAnalysis(
                java_version=self._extract_java_version(analysis_data),
                spring_boot_version=self._extract_spring_boot_version(analysis_data),
                dependencies=self._extract_dependencies(analysis_data),
                build_tool="maven"  # For now assuming Maven, can be extended
            )
            
            logger.info("Project analysis completed", 
                       extra_data={"analysis": project_analysis.dict()})
            
            return project_analysis
            
        except Exception as e:
            logger.error(f"Error during project analysis: {str(e)}")
            return None
            
    def _extract_java_version(self, analysis_data: str) -> str:
        # Implementation to extract Java version from analysis data
        # This is a placeholder - actual implementation would parse the analysis_data
        return "11"  # Default fallback
        
    def _extract_spring_boot_version(self, analysis_data: str) -> Optional[str]:
        # Implementation to extract Spring Boot version if present
        # This is a placeholder - actual implementation would parse the analysis_data
        return "2.7.0"  # Default fallback
        
    def _extract_dependencies(self, analysis_data: str) -> dict:
        # Implementation to extract dependencies
        # This is a placeholder - actual implementation would parse the analysis_data
        return {} 

async def analyze_project(
    sessions: SessionPair,
    preferences: UserPreferences
) -> Optional[ProjectAnalysis]:
    """
    Analyze project structure and dependencies.
    Pure function that takes sessions and preferences and returns analysis.
    """
    try:
        logger.info(f"Starting project analysis for directory: {preferences.project_directory}")
        
        analysis_data = await get_maven_analysis(sessions, preferences.project_directory)
        if not analysis_data:
            return None
            
        project_analysis = create_project_analysis(analysis_data)
        
        logger.info(f"Project analysis completed with analysis: {project_analysis.dict()}")
        
        return project_analysis
        
    except Exception as e:
        logger.error(f"Error during project analysis: {str(e)}")
        return None

async def get_maven_analysis(
    sessions: SessionPair,
    project_dir: str
) -> Optional[AnalysisData]:
    """Get raw analysis data from Maven tools."""
    try:
        _, maven_session = sessions
        maven_result = await maven_session.call_tool("analyzeProject")
        
        if not maven_result:
            logger.error("Failed to analyze project with Maven tools")
            return None
            
        # Find all pom files in the project
        pom_files = find_pom_files(project_dir)
        if not pom_files:
            logger.error(f"No pom.xml files found in project directory: {project_dir}")
            return None
            
        return AnalysisData(
            content=maven_result.content[0].text,
            metadata=maven_result.metadata if hasattr(maven_result, 'metadata') else {},
            pom_files=pom_files
        )
        
    except Exception as e:
        logger.error(f"Error getting Maven analysis: {str(e)}")
        return None

def create_project_analysis(analysis_data: AnalysisData) -> ProjectAnalysis:
    """Create ProjectAnalysis from raw analysis data."""
    return ProjectAnalysis(
        java_version=extract_java_version(analysis_data),
        spring_boot_version=extract_spring_boot_version(analysis_data),
        dependencies=extract_dependencies(analysis_data),
        build_tool="maven"
    )

def extract_java_version(analysis_data: AnalysisData) -> str:
    """Extract Java version from analysis data using maven_op implementation."""
    java_versions = set()
    
    for pom_file in analysis_data.pom_files:
        version = maven_extract_jdk(pom_file)
        if version:
            java_versions.add(version)
            logger.debug(f"Found Java version {version} in {pom_file}")
            
    # Return the minimum version found or default to "11"
    result = min(java_versions) if java_versions else "11"
    logger.info(f"Selected Java version: {result}")
    return result

def extract_spring_boot_version(analysis_data: AnalysisData) -> Optional[str]:
    """Extract Spring Boot version from analysis data using maven_op implementation."""
    spring_versions = set()
    
    for pom_file in analysis_data.pom_files:
        version = maven_extract_spring_boot(pom_file)
        if version:
            spring_versions.add(version)
            logger.debug(f"Found Spring Boot version {version} in {pom_file}")
            
    # Return the minimum version found or None
    result = min(spring_versions) if spring_versions else None
    logger.info(f"Selected Spring Boot version: {result}")
    return result

def extract_dependencies(analysis_data: AnalysisData) -> Dict[str, str]:
    """Extract dependencies from analysis data using pom.xml parsing."""
    dependencies = {}
    
    for pom_file in analysis_data.pom_files:
        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()
            ns = {"mvn": "http://maven.apache.org/POM/4.0.0"}
            
            # Extract dependencies from pom.xml
            deps = root.findall(".//mvn:dependencies/mvn:dependency", ns)
            for dep in deps:
                group_id = dep.find("mvn:groupId", ns)
                artifact_id = dep.find("mvn:artifactId", ns)
                version = dep.find("mvn:version", ns)
                
                if group_id is not None and artifact_id is not None:
                    key = f"{group_id.text}:{artifact_id.text}"
                    if version is not None:
                        dependencies[key] = version.text
                    else:
                        dependencies[key] = "managed"  # Version managed by parent pom
                        
        except Exception as e:
            logger.error(f"Error extracting dependencies from {pom_file}: {str(e)}")
            continue
            
    logger.info(f"Extracted {len(dependencies)} dependencies")
    return dependencies 