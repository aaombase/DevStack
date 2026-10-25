from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet, SprintViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("sprints", SprintViewSet, basename="sprint")

urlpatterns = router.urls
