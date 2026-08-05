import importlib
from pathlib import Path


class Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class OpportunitiesStreamlit:
    def __init__(self, mode: str = "Browse opportunities") -> None:
        self.headers: list[str] = []
        self.mode = mode
        self.session_state = {}

    def header(self, value: str) -> None:
        self.headers.append(value)

    def segmented_control(self, label, options, key):
        self.segmented_args = (label, options, key)
        self.session_state[key] = self.mode
        return self.mode


def test_opportunities_view_imports_successfully() -> None:
    assert importlib.import_module("app.views.opportunities_page")


def test_opportunity_components_import_without_circular_dependencies() -> None:
    modules = [
        "app.components.opportunity_browse",
        "app.components.opportunity_form",
        "app.components.opportunity_detail",
        "app.components.opportunity_product_editor",
        "app.opportunity_ui_helpers",
        "app.opportunity_form_state",
    ]

    for module in modules:
        assert importlib.import_module(module)


def test_no_streamlit_pages_directory_is_created() -> None:
    assert not Path("app/pages").exists()


def test_opportunities_page_coordinates_expected_sections(monkeypatch) -> None:
    import app.views.opportunities_page as opportunities_page

    fake_st = OpportunitiesStreamlit()
    calls: list[str] = []
    monkeypatch.setattr(opportunities_page, "st", fake_st)
    monkeypatch.setattr(opportunities_page, "render_flash_message", lambda: calls.append("flash"))
    monkeypatch.setattr(opportunities_page, "render_browse_opportunities", lambda: calls.append("browse"))
    monkeypatch.setattr(opportunities_page, "render_add_opportunity_form", lambda: calls.append("add"))
    monkeypatch.setattr(opportunities_page, "render_opportunity_detail", lambda: calls.append("detail"))

    opportunities_page.render_opportunities_page()

    assert fake_st.headers == ["Opportunities"]
    assert fake_st.segmented_args == (
        "Opportunity section",
        ("Browse opportunities", "Add opportunity", "Opportunity detail"),
        "opportunity_page_mode",
    )
    assert calls == ["flash", "browse"]


def test_opportunities_page_routes_detail_mode(monkeypatch) -> None:
    import app.views.opportunities_page as opportunities_page

    fake_st = OpportunitiesStreamlit(mode="Opportunity detail")
    calls: list[str] = []
    monkeypatch.setattr(opportunities_page, "st", fake_st)
    monkeypatch.setattr(opportunities_page, "render_flash_message", lambda: calls.append("flash"))
    monkeypatch.setattr(opportunities_page, "render_browse_opportunities", lambda: calls.append("browse"))
    monkeypatch.setattr(opportunities_page, "render_add_opportunity_form", lambda: calls.append("add"))
    monkeypatch.setattr(opportunities_page, "render_opportunity_detail", lambda: calls.append("detail"))

    opportunities_page.render_opportunities_page()

    assert calls == ["flash", "detail"]


def test_custom_navigation_recognizes_opportunities() -> None:
    import app.ui as ui

    assert ui.PAGE_OPPORTUNITIES == "Opportunities"
    assert "Opportunities" in ui.NAVIGATION_PAGES
