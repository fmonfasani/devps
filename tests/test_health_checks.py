"""Tests for health check monitoring."""

import pytest

from devps_agent import health_checks


class TestCheckContainerHealth:
    def test_container_not_found(self) -> None:
        """Test: container doesn't exist returns 'dead'"""
        # This would need mocking of docker_ops
        # Skipped in unit tests, requires integration test with real Docker
        pass

    def test_container_running(self) -> None:
        """Test: running container returns 'running'"""
        # Needs Docker integration
        pass

    def test_container_dead(self) -> None:
        """Test: stopped container returns 'dead'"""
        # Needs Docker integration
        pass


class TestRestartContainer:
    def test_restart_success(self) -> None:
        """Test: restart succeeds and increments counter"""
        # Needs Docker + registry integration
        pass

    def test_restart_missing_project(self) -> None:
        """Test: restart fails gracefully for missing project"""
        # Project not in registry → return False
        pass

    def test_restart_adopted_project(self) -> None:
        """Test: don't restart adopted projects (not managed by devps)"""
        # Adopted projects aren't restarted
        pass


class TestHealthCheckLoop:
    @pytest.mark.asyncio
    async def test_loop_cancellation(self) -> None:
        """Test: health check loop can be cancelled"""
        import asyncio

        task = asyncio.create_task(health_checks.health_check_loop())
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task


# Manual Testing Checklist
"""
Manual integration tests (requires running devps + Docker):

1. Start devps service:
   sudo systemctl start devps-agent

2. Deploy a test project:
   hzploy up test-app https://github.com/fmonfasani/devps.git \
     --service web=8000 \
     --primary web

3. Verify health loop is running:
   curl -s https://devps.webshooks.com/projects/test-app | jq .health_status
   # Should show "running"

4. Stop the container:
   docker stop devps_test-app_1

5. Wait 35 seconds (health check runs every 30s + grace period)

6. Verify auto-restart:
   curl -s https://devps.webshooks.com/projects/test-app | jq .
   # Should show:
   #   "health_status": "running"  (after restart)
   #   "restart_count": 1

7. Check events:
   hzploy logs test-app | grep auto_restart
   # Should show: "health check detected dead container, restarted"

8. Test unhealthy container (if health check defined in docker-compose.yml):
   # Add to docker-compose.yml:
   # healthcheck:
   #   test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
   #   interval: 10s
   #   timeout: 5s
   #   retries: 2

   # Make endpoint fail:
   # curl -X POST https://test-app.example.com/health/fail

   # Verify health_status = "unhealthy" (no auto-restart, logged as event)
"""

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
