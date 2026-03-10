import asyncio
from brainstorm.app import run_from_config
from brainstorm.llm import make_invoke

async def main():
    invoke = make_invoke()  # configure em brainstorm/llm.py com o seu SK
    result = await run_from_config("config/meeting.toml", invoke)

    print(result["final_text"])
    print("\nTurns used:", result["turns_used"])

if __name__ == "__main__":
    asyncio.run(main())
