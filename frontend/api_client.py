"""Typed HTTP boundary between the Streamlit dashboard and FastAPI."""

from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.app.schemas.analytics import ExperimentResponse, FunnelResponse, MetricsResponse


class ApiClientError(Exception):
    """A display-safe failure returned by the analytics API."""


class ApiRequestError(ApiClientError):
    """The API could not be reached or returned an unsuccessful response."""


class ApiResponseError(ApiClientError):
    """The API response did not match the expected public contract."""


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


@dataclass(frozen=True)
class ApiClient:
    """Fetch dashboard data without exposing database credentials to the frontend."""

    base_url: str
    timeout_seconds: float = 10.0

    def get_metrics(
        self,
        start_time: datetime,
        end_time: datetime,
        granularity: str,
        experiment_group: str | None,
    ) -> MetricsResponse:
        params = self._time_params(start_time, end_time, experiment_group)
        params["granularity"] = granularity
        return self._get("/api/metrics", params, MetricsResponse)

    def get_funnel(
        self, start_time: datetime, end_time: datetime, experiment_group: str | None
    ) -> FunnelResponse:
        return self._get(
            "/api/funnel",
            self._time_params(start_time, end_time, experiment_group),
            FunnelResponse,
        )

    def get_experiment(self, start_time: datetime, end_time: datetime) -> ExperimentResponse:
        return self._get(
            "/api/experiment",
            self._time_params(start_time, end_time, experiment_group=None),
            ExperimentResponse,
        )

    @staticmethod
    def _time_params(
        start_time: datetime, end_time: datetime, experiment_group: str | None
    ) -> dict[str, str]:
        params = {"start_time": start_time.isoformat(), "end_time": end_time.isoformat()}
        if experiment_group is not None:
            params["experiment_group"] = experiment_group
        return params

    def _get(
        self, path: str, params: dict[str, str], response_model: type[ResponseModel]
    ) -> ResponseModel:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(f"{self.base_url.rstrip('/')}{path}", params=params)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ApiRequestError("请求超时，请检查后端服务后重试。") from exc
        except httpx.HTTPStatusError as exc:
            raise ApiRequestError(self._http_error_message(exc.response)) from exc
        except httpx.RequestError as exc:
            raise ApiRequestError("无法连接后端服务，请检查 API 地址和网络。") from exc

        try:
            return response_model.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            raise ApiResponseError("后端返回的数据格式异常，请稍后重试。") from exc

    @staticmethod
    def _http_error_message(response: httpx.Response) -> str:
        if response.status_code == 422:
            return "筛选条件无效，请调整时间范围或粒度后重试。"
        if response.status_code == 503:
            return "分析数据暂不可用，请稍后重试。"
        return f"后端服务请求失败（HTTP {response.status_code}）。"
