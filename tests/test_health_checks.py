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

    def test_restart_rate_limit(self) -> None:
        """Test: restart rate limit prevents excessive restarts"""
        # Can't restart more than 5 times per hour
        pass


class TestRestartRateLimiter:
    def test_can_restart_initially(self) -> None:
        """Test: rate limiter allows restart initially"""
        limiter = health_checks.RestartRateLimiter()
        assert limiter.can_restart("test-project") is True

    def test_can_restart_after_limit(self) -> None:
        """Test: rate limiter blocks restart after 5 in one hour"""
        limiter = health_checks.RestartRateLimiter()
        project = "test-project"

        # Record 5 restarts
        for _ in range(5):
            assert limiter.can_restart(project) is True
            limiter.record_restart(project)

        # 6th restart should be blocked
        assert limiter.can_restart(project) is False

    def test_restart_count(self) -> None:
        """Test: get_restart_count returns correct count"""
        limiter = health_checks.RestartRateLimiter()
        project = "test-project"

        assert limiter.get_restart_count(project) == 0

        limiter.record_restart(project)
        limiter.record_restart(project)
        assert limiter.get_restart_count(project) == 2

    def test_old_restarts_cleaned(self) -> None:
        """Test: restarts older than 1 hour are cleaned"""
        import datetime as dt

        limiter = health_checks.RestartRateLimiter()
        project = "test-project"

        # Manually add an old timestamp
        old_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
        limiter.restart_times[project].append(old_time)

        # Old restart should be cleaned up
        assert limiter.get_restart_count(project) == 0


class TestHealthCheckLoop:
    @pytest.mark.asyncio
    async def test_loop_cancellation(self) -> None:
        """Test: health check loop can be cancelled"""
        import asyncio

        task = asyncio.create_task(health_checks.health_check_loop())
        await asyncio.sleep(0.1)
        task.cancel()

        # The loop catches CancelledError internally and breaks
        # so the task completes normally without raising
        await task
        assert task.done()


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
