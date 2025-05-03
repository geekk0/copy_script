import logging

from enhance_backend.models import Package
from fastapi import APIRouter, HTTPException
from tortoise.exceptions import DoesNotExist

from enhance_backend.db_manager import DatabaseManager
from enhance_backend.schemas import PackageResponse
from enhance_backend.utils import logger


packages_router = APIRouter(prefix="/packages")

db_manager = DatabaseManager()


@packages_router.get("/list")
async def get_all_packages() -> list[PackageResponse]:
    try:
        packages = await Package.all()
        package_responses = [PackageResponse.model_validate(p)
                             for p in packages]
        return package_responses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
#
#
# @packages_router.post("/add")
# async def add_package(package_data: PackageRequest) -> PackageResponse:
#     try:
#         package = await db_manager.add_package(package_data)
#         return package
#     except Exception as e:
#         print(e)
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @packages_router.delete("")
# async def remove_package(package_id: int) -> dict[str, str]:
#     try:
#         await db_manager.delete_package(package_id)
#         return {"message": "Package removed successfully"}
#     except DoesNotExist:
#         raise HTTPException(status_code=404, detail="Package not found")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
#
@packages_router.get("/task_id")
async def get_package_by_task_id(task_id: int) -> PackageResponse | None:
    try:
        package = await db_manager.get_package_by_task_id(task_id)
        return package
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Package not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# @packages_router.get("/purchased")
# async def get_user_purchased_packages() -> list[PackageResponse]:
#     try:
#         # packages = await db_manager.get_all_purchased_packages()
#
#         return packages
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))