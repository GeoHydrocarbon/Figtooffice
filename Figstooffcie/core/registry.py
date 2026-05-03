class ModuleRegistry:
    def __init__(self) -> None:
        self._modules = {}

    def register(self, module_service) -> None:
        self._modules[module_service.manifest.module_id] = module_service

    def get(self, module_id: str):
        return self._modules[module_id]

    def all(self) -> list:
        return list(self._modules.values())
