from rest_framework.routers import DefaultRouter

from .views import ActivityViewSet, TaskViewSet

router = DefaultRouter()
router.register("tasks", TaskViewSet, basename="task")
router.register("activity", ActivityViewSet, basename="activity")

urlpatterns = router.urls
