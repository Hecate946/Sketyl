import os

import json
import config
import asyncio
import asyncpg


class DB:
    """
    Attempts to create a postgres database connection,
    falls back to json.
    """

    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.json = None
        self.loop.run_until_complete(self.__init__db())

    async def __init__db(self):
        try:
            self.cxn = await asyncpg.create_pool(config.POSTGRES.uri)
        except:
            # Unable to create postgres connection
            self.json = True

        await self.scriptexec()

    async def scriptexec(self):
        if self.json:
            if not os.path.exists("./db.json"):
                with open("./db.json", "w") as fp:
                    fp.write(r"{}")
        else:
            # We execute the SQL scripts to make sure we have all our tables.
            for script in os.listdir("./scripts"):
                with open("./scripts/" + script, "r", encoding="utf-8") as script:
                    await self.cxn.execute(script.read())

    async def insert_user(self, user_id, token_info):
        if self.json:
            with open("./db.json", "r") as fp:
                db = json.load(fp)
                db[user_id] = token_info
            with open("./db.json", "w") as fp:
                json.dump(db, fp, indent=2)

        else:
            query = """                
                    INSERT INTO spotify_auth
                    VALUES ($1, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET token_info = $2
                    WHERE spotify_auth.user_id = $1;
                    """
            await self.cxn.execute(query, user_id, json.dumps(token_info))

    async def delete_user(self, user_id):
        if self.json:
            with open("./db.json", "r") as fp:
                db = json.load(fp)
                db.pop(user_id, None)
            with open("./db.json", "w") as fp:
                json.dump(db, fp, indent=2)
        else:
            query = """
                DELETE FROM spotify_auth
                WHERE user_id = $1
                """
            await self.cxn.execute(query, user_id)

    async def fetch_user(self, user_id):
        if self.json:
            with open("./db.json", "r") as fp:
                db = json.load(fp)
                token_info = db.get(user_id)
        else:
            query = """
                    SELECT token_info
                    FROM spotify_auth
                    WHERE user_id = $1;
                    """
            token_info = await self.cxn.fetchval(query, user_id)
            if token_info:
                token_info = json.loads(token_info)

        return token_info
