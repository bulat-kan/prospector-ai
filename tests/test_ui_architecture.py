import importlib
from pathlib import Path
from types import SimpleNamespace

from app.form_state import ADD_COMPANY_DEFAULTS, ADD_CONTACT_DEFAULTS


class Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class RoutingStreamlit:
    def __init__(self, page: str = "Dashboard") -> None:
        self.page = page
        self.titles: list[str] = []

    @property
    def sidebar(self) -> Context:
        return Context()

    def set_page_config(self, **kwargs) -> None:
        self.page_config = kwargs

    def title(self, value: str) -> None:
        self.titles.append(value)

    def caption(self, value: str) -> None:
        self.caption_value = value

    def header(self, value: str) -> None:
        self.header_value = value

    def radio(self, label, options, index=0):
        self.radio_args = (label, options, index)
        return self.page


class DashboardStreamlit:
    @property
    def sidebar(self) -> Context:
        return Context()

    def subheader(self, value: str) -> None:
        self.subheader_value = value

    def selectbox(self, label, options, index=0, format_func=None, key=None):
        del label, format_func, key
        return options[index]

    def button(self, *args, **kwargs) -> bool:
        del args, kwargs
        return False

    def header(self, value: str) -> None:
        self.header_value = value

    def error(self, value: str) -> None:
        self.error_value = value


class CompaniesStreamlit:
    def __init__(self) -> None:
        self.headers: list[str] = []

    def header(self, value: str) -> None:
        self.headers.append(value)

    def tabs(self, names):
        self.tab_names = names
        return [Context() for _ in names]


def test_ui_modules_import_without_circular_dependencies() -> None:
    modules = [
        "app.ui",
        "app.views.dashboard_page",
        "app.views.companies_page",
        "app.components.flash_messages",
        "app.components.company_form",
        "app.components.company_browse",
        "app.components.company_overview",
        "app.components.location_forms",
        "app.components.contact_forms",
        "app.components.referral_forms",
    ]

    for module in modules:
        assert importlib.import_module(module)


def test_streamlit_reserved_pages_package_is_not_used() -> None:
    assert not Path("app/pages").exists()


def test_top_level_routing_recognizes_dashboard(monkeypatch) -> None:
    import app.ui as ui

    fake_st = RoutingStreamlit(page=ui.PAGE_DASHBOARD)
    called = SimpleNamespace(dashboard=False, companies=False)
    monkeypatch.setattr(ui, "st", fake_st)
    monkeypatch.setattr(ui, "render_dashboard_page", lambda: setattr(called, "dashboard", True))
    monkeypatch.setattr(ui, "render_companies_page", lambda: setattr(called, "companies", True))

    ui.main()

    assert called.dashboard is True
    assert called.companies is False


def test_top_level_routing_recognizes_companies(monkeypatch) -> None:
    import app.ui as ui

    fake_st = RoutingStreamlit(page=ui.PAGE_COMPANIES)
    called = SimpleNamespace(dashboard=False, companies=False)
    monkeypatch.setattr(ui, "st", fake_st)
    monkeypatch.setattr(ui, "render_dashboard_page", lambda: setattr(called, "dashboard", True))
    monkeypatch.setattr(ui, "render_companies_page", lambda: setattr(called, "companies", True))

    ui.main()

    assert called.dashboard is False
    assert called.companies is True


def test_dashboard_render_function_invokes_with_mocked_dependencies(monkeypatch) -> None:
    import app.views.dashboard_page as dashboard_page

    fake_st = DashboardStreamlit()
    monkeypatch.setattr(dashboard_page, "st", fake_st)
    monkeypatch.setattr(dashboard_page, "demo_month_exists", lambda: True)
    monkeypatch.setattr(dashboard_page, "load_dashboard_data", lambda year, month: (_ for _ in ()).throw(ValueError("mocked error")))

    dashboard_page.render_dashboard_page()

    assert fake_st.header_value == "July 2026"
    assert fake_st.error_value == "mocked error"


def test_companies_render_function_invokes_with_mocked_components(monkeypatch) -> None:
    import app.views.companies_page as companies_page

    fake_st = CompaniesStreamlit()
    calls: list[str] = []
    monkeypatch.setattr(companies_page, "st", fake_st)
    monkeypatch.setattr(companies_page, "render_flash_message", lambda: calls.append("flash"))
    monkeypatch.setattr(companies_page, "render_browse_companies", lambda: calls.append("browse"))
    monkeypatch.setattr(companies_page, "render_add_company_form", lambda: calls.append("add"))
    monkeypatch.setattr(companies_page, "render_company_detail", lambda: calls.append("detail"))

    companies_page.render_companies_page()

    assert fake_st.headers == ["Companies"]
    assert calls == ["flash", "browse", "add", "detail"]


def test_form_state_keys_remain_stable_after_ui_refactor() -> None:
    expected_add_company_keys = {
        "add_company_name",
        "add_company_phone",
        "add_company_website",
        "add_company_industry",
        "add_company_other_industry",
        "add_company_lead_source",
        "add_company_notes",
        "add_company_referral_mode",
        "add_company_referral_partner_id",
        "add_company_partner_first",
        "add_company_partner_last",
        "add_company_partner_org",
        "add_company_partner_role",
        "add_company_partner_phone",
        "add_company_partner_email",
        "add_company_partner_registered",
        "add_company_partner_reference",
        "add_company_partner_notes",
        "add_company_referral_phone_error",
        "add_company_referral_email_error",
    }
    expected_contact_keys = {
        "first_name",
        "last_name",
        "title_selection",
        "other_title",
        "location_id",
        "phone",
        "email",
        "decision_role",
        "is_primary_contact",
        "notes",
    }

    assert expected_add_company_keys <= set(ADD_COMPANY_DEFAULTS)
    assert expected_contact_keys <= set(ADD_CONTACT_DEFAULTS)
