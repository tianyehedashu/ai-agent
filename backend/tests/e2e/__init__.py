"""
E2E (End-to-End) 测试

这些测试需要完整的运行环境，不使用 Mock，真正调用 API。

运行方式:
    make test-e2e          # 启动环境后运行

注意:
    - 需要先启动 docker-compose (数据库、Redis)
    - 需要后端服务运行中
    - make test 不会执行这些测试
"""
