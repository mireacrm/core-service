from datetime import UTC

import grpc
from mirea.common.v1 import common_pb2
from mirea.core.v1 import core_pb2, core_pb2_grpc
from mireacrm_common.errors import InvalidArgumentError
from mireacrm_common.lifespan import AppContext
from mireacrm_common.rpc import Registration, parse_uuid, to_timestamp

from app import domain
from app.rpc import mapping


class CoreServicer(core_pb2_grpc.CoreServiceServicer):
    def __init__(self, context: AppContext) -> None:
        self._context = context

    async def GetBranch(self, request, _context):
        async with self._context.session() as session:
            branch = await domain.get_branch(session, parse_uuid(request.branch_id, "branch_id"))
        return core_pb2.GetBranchResponse(branch=mapping.branch(branch))

    async def GetEmployeeSchedule(self, request, _context):
        if not request.period.HasField("start_at") or not request.period.HasField("end_at"):
            raise InvalidArgumentError("period обязателен")

        async with self._context.session() as session:
            employee, shifts = await domain.get_schedule(
                session,
                parse_uuid(request.employee_id, "employee_id"),
                request.period.start_at.ToDatetime(tzinfo=UTC),
                request.period.end_at.ToDatetime(tzinfo=UTC),
            )

        return core_pb2.GetEmployeeScheduleResponse(
            employee=mapping.employee(employee),
            shifts=[
                core_pb2.WorkShift(
                    period=common_pb2.TimeRange(
                        start_at=to_timestamp(shift.starts_at),
                        end_at=to_timestamp(shift.ends_at),
                    )
                )
                for shift in shifts
            ],
        )

    async def ListEmployees(self, request, _context):
        async with self._context.session() as session:
            employees, next_cursor = await domain.list_employees(
                session,
                parse_uuid(request.branch_id, "branch_id"),
                mapping.ROLE_FROM_PROTO.get(request.role),
                request.page.limit or 50,
                request.page.cursor or None,
            )

        return core_pb2.ListEmployeesResponse(
            employees=[mapping.employee(item) for item in employees],
            page=common_pb2.PageResponse(next_cursor=next_cursor),
        )


def registration(context: AppContext) -> Registration:
    def register(server: grpc.aio.Server) -> None:
        core_pb2_grpc.add_CoreServiceServicer_to_server(CoreServicer(context), server)

    return Registration(
        register=register,
        full_name=core_pb2.DESCRIPTOR.services_by_name["CoreService"].full_name,
    )
