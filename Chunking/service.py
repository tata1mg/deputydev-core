import multiprocessing

from relevant_chunks_finder import run_main
from pydantic import BaseModel
import asyncio
from websockets.asyncio.server import serve
import json


class Params(BaseModel):
    repo_path: str
    auth_token: str
    query: str


async def process_task(websocket) -> None:
    try:
        while True:
            message = await websocket.recv()
            params = json.loads(message)
            if params.get("quit"):
                break
            params = Params(**params)
            await websocket.send("Task Started")
            relevant_chunks = await run_main(params)
            await websocket.send(f"Number of received relevant chunks: {len(relevant_chunks)}")
            if relevant_chunks:
                await websocket.send(f"Sample Relevant Chunk: {relevant_chunks[0].content}")
    except Exception as e:
        await websocket.send(f"Error occurred: {str(e)}")


async def main():
    async with serve(process_task, "localhost", 8765):
        print("WebSocket server running on ws://localhost:8765")
        await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    asyncio.run(main())
