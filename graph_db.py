# import asyncio
# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# from config import settings
# from graph_run import builder   # 复用建好的图，只换存档器
#
# async def main():
#     async with AsyncPostgresSaver.from_conn_string(settings.postgres_uri) as checkpointer:
#         await checkpointer.setup()
#
#         graph = builder.compile(checkpointer=checkpointer)
#         config = {"configurable": {"thread_id": "user-001"}}
#
#         result = await graph.ainvoke({"topic_direction": "无畏契约新手攻略"}, config)
#         print(result)
#
# asyncio.run(main())
