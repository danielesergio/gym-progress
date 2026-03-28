import yaml
from typing import Any, Dict, List, Set


class DietParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = self._load_file()

    def _load_file(self) -> Dict[str, Any]:
        with open(self.file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _extract_from_alimenti(self, node: Any, collected: Set[str]) -> None:
        """
        Estrae solo i 'nome' presenti dentro blocchi 'alimenti'.
        """
        if isinstance(node, dict):
            # Caso specifico: siamo dentro "alimenti"
            if "alimenti" in node and isinstance(node["alimenti"], list):
                for alimento in node["alimenti"]:
                    if isinstance(alimento, dict) and "nome" in alimento:
                        collected.add(alimento["nome"])

            # Continua la ricorsione
            for value in node.values():
                self._extract_from_alimenti(value, collected)

        elif isinstance(node, list):
            for item in node:
                self._extract_from_alimenti(item, collected)

    def get_unique_foods(self) -> List[str]:
        unique_foods: Set[str] = set()
        self._extract_from_alimenti(self.data, unique_foods)
        return sorted(unique_foods)


if __name__ == "__main__":
    file_path = r"C:\Users\danie\AndroidStudioProjects\gym\data\output\diet_acdf8cc9.yaml"

    parser = DietParser(file_path)  # path al tuo file
    foods = parser.get_unique_foods()

    for food in foods:
        print(food)