class GlobalConstant:
    try:
        import yaml as yaml_module
        YAML_OK = True
    except ImportError:
        yaml_module = None
        YAML_OK = False