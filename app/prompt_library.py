class PromptLibraryError(ValueError):
    """Prompt 库查询或渲染失败时抛出。"""


class PromptTemplate:
    def __init__(
        self,
        name: str,
        version: str,
        content: str,
        description: str = "",
    ):
        if not name.strip():
            raise ValueError("Prompt 名称不能为空")
        if not version.strip():
            raise ValueError("Prompt 版本不能为空")

        self.name = name
        self.version = version
        self.content = content
        self.description = description

    def render(self, **variables) -> str:
        try:
            return self.content.format(**variables)
        except KeyError as exc:
            raise PromptLibraryError(
                f"渲染 Prompt {self.name} 缺少变量: {exc}"
            ) from exc


class PromptLibrary:
    def __init__(self):
        self._templates: dict[tuple[str, str], PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        if not isinstance(template, PromptTemplate):
            raise TypeError("只能注册 PromptTemplate")

        key = (template.name, template.version)

        if key in self._templates:
            raise PromptLibraryError(
                f"Prompt 已存在：{template.name}:{template.version}"
            )

        self._templates[key] = template

    def get(self, prompt_name: str, version: str = "v1") -> PromptTemplate:
        template = self._templates.get((prompt_name, version))

        if template is None:
            raise PromptLibraryError(f"未知 Prompt：{prompt_name}:{version}")

        return template

    def render(
        self,
        prompt_name: str,
        version: str = "v1",
        **variables,
    ) -> str:
        return self.get(prompt_name, version).render(**variables)

    def list_templates(self) -> list[PromptTemplate]:
        return sorted(
            self._templates.values(),
            key=lambda item: (item.name, item.version),
        )