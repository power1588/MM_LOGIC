from enum import Enum

class RiskLevel(Enum):
    """风险等级"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL" 