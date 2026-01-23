"""
配置源单元测试
"""

import pytest

from libs.config.sources.base import ConfigSource
from libs.config.sources.toml_source import AgentTomlSource, TomlConfigSource


class TestTomlConfigSource:
    """TomlConfigSource 测试"""

    def test_load_existing_config(self, tmp_path):
        """测试: 加载存在的配置"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "test.toml").write_text(
            '[sandbox]\nmode = "docker"\n',
            encoding="utf-8",
        )

        source = TomlConfigSource(config_dir)
        data = source.load("test")

        assert data is not None
        assert data["sandbox"]["mode"] == "docker"

    def test_load_nonexistent_config(self, tmp_path):
        """测试: 加载不存在的配置返回 None"""
        source = TomlConfigSource(tmp_path)
        data = source.load("nonexistent")

        assert data is None

    def test_exists(self, tmp_path):
        """测试: exists 方法"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "exists.toml").write_text("", encoding="utf-8")

        source = TomlConfigSource(config_dir)

        assert source.exists("exists") is True
        assert source.exists("not_exists") is False

    def test_list_available(self, tmp_path):
        """测试: 列出可用配置"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config1.toml").write_text("", encoding="utf-8")
        (config_dir / "config2.toml").write_text("", encoding="utf-8")
        (config_dir / "_hidden.toml").write_text("", encoding="utf-8")

        source = TomlConfigSource(config_dir)
        available = source.list_available()

        assert "config1" in available
        assert "config2" in available
        assert "_hidden" not in available  # 下划线开头的被跳过

    def test_save_config(self, tmp_path):
        """测试: 保存配置"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        source = TomlConfigSource(config_dir)
        result = source.save("new_config", {"key": "value"})

        assert result is True
        assert (config_dir / "new_config.toml").exists()

    def test_delete_config(self, tmp_path):
        """测试: 删除配置"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "to_delete.toml").write_text("", encoding="utf-8")

        source = TomlConfigSource(config_dir)

        assert source.exists("to_delete") is True
        result = source.delete("to_delete")
        assert result is True
        assert source.exists("to_delete") is False


class TestAgentTomlSource:
    """AgentTomlSource 测试"""

    def test_load_agent_config(self, tmp_path):
        """测试: 加载 Agent 配置"""
        agents_dir = tmp_path / "agents"
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "agent.toml").write_text(
            'extends = "python-dev"\n',
            encoding="utf-8",
        )

        source = AgentTomlSource(agents_dir)
        data = source.load("test-agent")

        assert data is not None
        assert data["extends"] == "python-dev"

    def test_list_agents(self, tmp_path):
        """测试: 列出有配置的 Agent"""
        agents_dir = tmp_path / "agents"

        # Agent 1 有配置
        agent1 = agents_dir / "agent1"
        agent1.mkdir(parents=True)
        (agent1 / "agent.toml").write_text("", encoding="utf-8")

        # Agent 2 没有配置
        agent2 = agents_dir / "agent2"
        agent2.mkdir(parents=True)

        source = AgentTomlSource(agents_dir)
        agents = source.list_available()

        assert "agent1" in agents
        assert "agent2" not in agents


class TestConfigSourceInterface:
    """ConfigSource 接口测试"""

    def test_is_abstract(self):
        """测试: ConfigSource 是抽象类"""
        with pytest.raises(TypeError):
            ConfigSource()  # type: ignore
