"""Navigation metadata for the dashboard application shell."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    description: str
    status: str = "available"


NAVIGATION_ITEMS = (
    NavigationItem("home", "Home", "经营总览"),
    NavigationItem("monitor", "Monitor", "指标监测"),
    NavigationItem("attribution", "Attribution", "营销归因", "planned"),
    NavigationItem("funnel", "Funnel", "漏斗诊断"),
    NavigationItem("customers", "Customers", "客户分析", "planned"),
    NavigationItem("experiments", "Experiments", "实验中心"),
    NavigationItem("creatives", "Creatives", "素材表现", "planned"),
    NavigationItem("integrations", "Integrations", "数据接入", "planned"),
)


def navigation_item(key: str) -> NavigationItem:
    return next(item for item in NAVIGATION_ITEMS if item.key == key)
