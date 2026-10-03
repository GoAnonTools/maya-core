from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"
IDENTITY_CONFIG_PATH = CONFIGS_DIR / "maya-identity.yaml"
CONTRACT_CONFIG_PATH = CONFIGS_DIR / "maya-contract.yaml"
MAYA_CONFIG_PATH = CONFIGS_DIR / "maya-config.yaml"
