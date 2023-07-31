import re
from functools import partial
from random import choice
from typing import Optional, cast

from nonebot import get_bot
from nonebot import CommandGroup
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageEvent, escape

from ._lang import text, LangType
from ._onebot import (
    UserID, GroupID,
    send_msg, get_msg, get_user_name,
    send_forward_msg, custom_forward_node,
    REPLY_PATTERN, SPECIAL_PATTERN
)
from ._store import JsonDict


text = partial(text, prefix="cave")
caves = JsonDict("caves.json", dict)
cave = CommandGroup("cave", aliases={"cav"})


@cave.command(tuple()).handle()
async def cave_random_handle(event: MessageEvent) -> None:
    await send_cave(
        cave_id=choice(list(caves.keys())),
        lang=event,
        user_id=event.user_id,
        group_id=getattr(event, "group_id", None)
    )


@cave.command("add").handle()
async def cave_add_handle(
    matcher: Matcher,
    event: MessageEvent,
    arg: Message = CommandArg()
) -> None:
    if founds := re.findall(REPLY_PATTERN, event.raw_message):
        data = await get_msg(founds[0])
        content = data["message"]
        user_id = data["sender"]["user_id"]
    else:
        content = str(arg).strip()
        user_id = event.user_id
    cave_id = 0
    while str(cave_id) in caves.keys():
        cave_id += 1
    cave_id = str(cave_id)
    caves[cave_id] = {"content": content, "user_id": user_id}
    await matcher.send(text(event, ".cave.add", cave_id=cave_id))


@cave.command("get").handle()
async def cave_get_handle(
    event: MessageEvent,
    arg: Message = CommandArg()
) -> None:
    await send_cave(
        cave_id=str(arg).strip(),
        lang=event,
        user_id=event.user_id,
        group_id=getattr(event, "group_id", None)
    )


@cave.command("comment", aliases={"cmt"}).handle()
async def cave_comment_handle(
    matcher: Matcher,
    event: MessageEvent,
    arg: Message = CommandArg()
) -> None:
    cave_id, content = str(arg).strip().split(maxsplit=1)
    if cave_id not in caves.keys():
        await matcher.finish(text(event, ".cave.non-exist", cave_id=cave_id))
    if "comments" not in caves[cave_id].keys():
        caves[cave_id]["comments"] = {}
    comment_id = len(caves[cave_id]["comments"])
    caves[cave_id]["comments"][comment_id] = {
        "user_id": event.user_id,
        "content": content,
        "time": event.time
    }
    await matcher.send(text(
        event, ".comment.add",
        cave_id=cave_id,
        comment_id=comment_id
    ))


@cave.command("remove", aliases={"rm"}).handle()
async def cave_remove_handle(
    matcher: Matcher,
    event: MessageEvent,
    arg: Message = CommandArg()
) -> None:
    comment_id = ""
    if " " in (cave_id := str(arg).strip()):
        cave_id, comment_id, *_ = cave_id.split()
    if cave_id not in caves.keys():
        await matcher.finish(text(event, ".cave.non-exist", cave_id=cave_id))
    if comment_id != "":    # remove comment
        comments = caves[cave_id].get("comments", {})
        if comment_id not in comments.keys():
            await matcher.finish(text(
                event, ".comment.non-exist",
                cave_id=cave_id,
                comment_id=comment_id
            ))
        if (str(event.user_id) in get_bot().config.superusers
                or event.user_id == comments[comment_id]["user_id"]):
            caves.pop(cave_id)
            await matcher.finish(text(
                event, ".comment.remove",
                cave_id=cave_id,
                comment_id=comment_id
            ))
        await matcher.send(text(
            event, ".comment.remove.no-permission",
            cave_id=cave_id,
            comment_id=comment_id
        ))
    else:                   # remove cave
        if (str(event.user_id) in get_bot().config.superusers
                or event.user_id == caves[cave_id]["user_id"]):
            caves.pop(cave_id)
            await matcher.finish(text(event, ".cave.remove", cave_id=cave_id))
        await matcher.send(text(
            event, ".cave.remove.no-permission",
            cave_id=cave_id
        ))


async def send_cave(
    cave_id: str,
    lang: LangType,
    group_id: Optional[GroupID] = None,
    user_id: Optional[UserID] = None
) -> None:
    send = partial(send_msg, user_id=user_id, group_id=group_id)
    if cave_id in caves.keys():
        message = caves[cave_id]
        user_id = message["user_id"]
        content = message["content"]
        sender = escape(await get_user_name(user_id, group_id))
        if re.search(SPECIAL_PATTERN, content):
            await send(Message(text(
                lang, ".cave.text.without-content",
                cave_id=cave_id,
                sender=sender
            )))
            await send(Message(content))
        else:
            await send(Message(text(
                lang, ".cave.text",
                cave_id=cave_id,
                content=content,
                sender=sender
            )))
        if comments := caves[cave_id].get("comments"):
            await send_forward_msg([
                await custom_forward_node(
                    (user_id := comment["user_id"]),
                    content=comment["content"],
                    name=text(
                        lang, ".comment.text",
                        sender=await get_user_name(user_id),
                        comment_id=comment_id
                    ),
                    group_id=group_id,
                    time=comment["time"]
                ) for comment_id, comment in cast(dict, comments).items()
            ], user_id=user_id, group_id=group_id)
    else:
        await send(text(lang, ".cave.non-exist", cave_id=cave_id))
