import asyncio
from brainstorm.config import log
from brainstorm.app import run_from_config
from brainstorm.llm import make_invoke

async def main():
    log("=== ARRANQUE ===")
    log("A criar invoke (ligação ao LLM)...")
    invoke = make_invoke()

    log("A lançar reunião...")
    result = await run_from_config("config/meeting.toml", invoke)

    print("\n" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)
    print(result["final_text"])
    print(f"\nTurns used: {result['turns_used']}")

if __name__ == "__main__":
    asyncio.run(main())
