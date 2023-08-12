from discord.ext import commands
from discord.ext.commands import param
import discord
import os
import wavelink
from wavelink.ext import spotify
from utilities import craft
import aiohttp
import math
import asyncio
import re
import datetime
import traceback

name = (os.path.basename(__file__)).replace(".py", "")


class Cog(commands.Cog, name=name):
    def __init__(self, bot):
        self.bot = bot
        self.preferred_channel = [None, False, True]
        self.modes = ["sc", "spt", "yt", "direct_mode", "soundcloud", "spt", "youtube"]
        self.blacklist = [803579319003512833]

    async def cog_after_invoke(self, ctx):
        if not self.preferred_channel[1] and self.preferred_channel[0] != ctx.channel:
            self.preferred_channel[0] = ctx.channel

    async def cog_check(self, ctx):
        return ctx.author.id not in self.blacklist

    @commands.command(aliases=["latency", "test", "ing"])
    async def ping(self, ctx):
        """\n    Tests the bot connection."""
        await ctx.reply(f"🏓 Pong! Latency is {round(self.bot.latency*1000, 2)}ms")

    @commands.command(aliases=["roblem", "problem"])
    @commands.cooldown(rate=1, per=120)
    async def report(self, ctx):
        """\n    Creates a connection/latency report to issu."""
        owner = self.bot.get_user(self.bot.owner_id)
        if owner:
            current_node = wavelink.NodePool.get_connected_node()
            await owner.send(
                f"A latency report was made by {ctx.author} ({ctx.author.mention})!\nCurrent timestamp: {discord.utils.utcnow()}\nWavelink node info:\n- uri: {current_node.uri if 'localhost' not in current_node.uri else f'{current_node.uri} (server main)'}\n- status: {current_node.status}\n- latency: {current_node.heartbeat}",
                silent=True,
            )
            return await ctx.reply("✅ Your report has been sent!")
        await ctx.reply(
            f"❌ Your report was not sent. Current timestamp: {discord.utils.utcnow()} | <@{self.bot.owner_id}>"
        )

    @commands.is_owner()
    @commands.command(aliases=["reload", "reload_extensions"])
    async def reload_cogs(self, ctx):
        """\n    (OWNER ONLY) Reloads the Music extension."""
        await ctx.reply("Reloading extensions!")
        try:
            return await self.bot.reload_cogs()
        except Exception as exc:
            print(exc)

    async def join_channel(
        self, ctx: commands.Context, channel: discord.VoiceChannel = None
    ) -> discord.Message:
        vc: wavelink.Player = ctx.voice_client

        if vc:
            await vc.move_to(channel)
            return await ctx.reply(f"➡ Switching to `{channel.name}`!")

        await channel.connect(cls=wavelink.Player, self_deaf=True)
        return await ctx.reply(f"🔊 Joining `{channel.name}`!")

    async def switch_preferred_channel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ) -> discord.Message:
        self.preferred_channel[0] = channel
        self.preferred_channel[1] = True
        return await ctx.reply(
            f"📝 Changed preferred announcement channel to `{channel.name}`!"
        )

    async def determine_channel_handling(
        self, ctx, channel: discord.VoiceChannel | discord.TextChannel
    ) -> discord.Message:
        if type(channel) == discord.VoiceChannel:
            return await self.join_channel(ctx, channel)
        elif type(channel) == discord.TextChannel:
            return await self.switch_preferred_channel(ctx, channel)
        return await ctx.reply(
            "You're not supposed to see this! <@471112338099929100> >> Could not determine channel type."
        )

    @commands.command(aliases=["move", "join", "switch", "set"])
    async def connect(
        self,
        ctx,
        channel: discord.TextChannel
        | None = param(
            description="\n    [Text Channel] The channel to switch the preferred announcement channel to.",
            default=None,
            displayed_default=None,
        ),
    ):
        """Joins the VC you are in or switches the preferred announcement channel to the given channel, if possible."""

        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        channel = channel or ctx.author.voice.channel
        force = "-force" in ctx.message.content or "-f" in ctx.message.content

        if type(channel) == discord.TextChannel:
            return await self.determine_channel_handling(ctx, channel)
        elif type(channel) == discord.VoiceChannel:
            if vc and vc.channel == channel:
                if force:
                    return await self.determine_channel_handling(ctx, channel)
                else:
                    return await ctx.reply(
                        '❓Are you sure you want to set the preferred announcement channel to a VC? use a "-force" on this command!'
                    )
            elif not vc:
                return await self.determine_channel_handling(ctx, channel)
            return await ctx.reply("🤓 Hey silly! I'm already here! (hi already here!)")
        else:
            return await ctx.reply(
                "🤓 Hey, silly! Join a voice channel so I know which one to join!"
            )

    async def resume_track(self, ctx) -> discord.Message:
        vc: wavelink.Player = ctx.voice_client

        if vc and vc.is_paused():
            await vc.resume()
            return await ctx.reply(
                f"▶ Resuming `{vc.current}` by **{vc.current.author}**!"
            )
        return await ctx.reply("❌ There is nothing to resume!")

    @commands.command(aliases=["continue"])
    async def resume(self, ctx):
        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        await self.resume_track(ctx)

    @commands.command(aliases=["quiet", "mute"])
    async def silence(
        self,
        ctx,
        value: str = param(
            description="\n    (opt.) {true/false} The value to set silence to. Otherwise toggles it.",
            default=None,
            displayed_default=None,
        ),
    ):
        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        if vc:
            self.preferred_channel[2] = (
                True
                if value.lower() == "true"
                else False
                if value.lower() == "false"
                else not self.preferred_channel[2]
            )
            if self.preferred_channel[2]:
                return await ctx.reply(
                    f"✉ Music announcements to {self.preferred_channel[0]} are now resumed."
                )
            return await ctx.reply(
                f"🤫 Music announcements to {self.preferred_channel[0]} are now silenced."
            )

        await ctx.message.add_reaction("❌")

    @commands.command(
        aliases=[
            "p",
            "start",
            "lay",
            "search",
        ]
    )
    async def play(
        self,
        ctx,
        mode: str
        | None = param(
            description="\n    (opt.) [string] {yt/spt/sc/direct_mode} The search mode to use.",
            default=None,
            displayed_default=None,
        ),
        *,
        search: str
        | None = param(
            description="\n    (opt.) [string] The search term/phrase or link to queue.",
            default=None,
            displayed_default=None,
        ),
    ) -> None:
        """\n    Searches for and plays a track. Joins or moves to your voice channel if the bot isn't in one or is alone, if needed."""
        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        channel = (
            vc.channel
            if vc and len(vc.channel.members) >= 2
            else ctx.author.voice.channel
        )

        if channel is None:
            return await ctx.reply("❓ What VC do I join? *[Join one for me to join!]*")

        if not vc or vc.channel != channel:
            message = await self.determine_channel_handling(ctx, channel)
            vc: wavelink.Player = ctx.voice_client
        else:
            message = None

        if not mode and vc.is_paused():
            return await self.resume_track(ctx)
        elif not mode:
            return (
                await message.edit(content="❓ Whatcha wanna play?")
                if message
                else await ctx.reply("❓ Whatcha wanna play?")
            )
        elif mode and not search:
            search = mode
            mode = "yt"
        elif mode.lower() not in self.modes:
            search = f"{mode} {search}"
            mode = "yt"
        else:
            mode = mode.lower()

        message = (
            await ctx.reply("⏳ Loading...")
            if not message
            else await message.edit(content=f"{message.content}\n\n⏳ Loading...")
        )

        TrackObject = await self.query_tracks(ctx, mode, search)

        if TrackObject is None:
            return await message.edit(
                content=f"{message.content}\n\n❌ Something wrong happened! Could not complete search.\n\n*This feature is in beta. Send all suggestions to @issu*"
            )
        elif type(TrackObject) == list:
            return await message.edit(
                f"{message.content}\n\n❌ Spotify tracks/playlists are currently not supported. Sorry!"
            )
        elif TrackObject is False:
            return await message.edit(
                content=f"{message.content}\n\n❌ Could not find your desired song, even with all the different searches!\n\n*This feature is in beta. Send all suggestions to @issu*"
            )

        if (
            type(TrackObject) == wavelink.YouTubePlaylist
            or type(TrackObject) == wavelink.SoundCloudPlaylist
        ):
            if vc.current:
                await message.edit(
                    content=f"{message.content}\n\n📃 Queued `{TrackObject}` starting at __Position #{len(vc.queue)+1}__"
                )
                return await vc.queue.put_wait(TrackObject)
            else:
                await message.edit(
                    content=f"{message.content}\n\n📃 Queued `{TrackObject}` starting at __Position #{len(vc.queue)}__"
                )
                await vc.queue.put_wait(TrackObject)

                return await vc.play(vc.queue.get())

        if vc.current:
            await message.edit(
                content=f"{message.content}\n\n📃 Queued `{TrackObject}` by **{TrackObject.author}** at __Position #{len(vc.queue)+1}__"
            )
            return vc.queue.put(TrackObject)
        else:
            await message.edit(content=f"{message.content}\n\n▶ Now playing! ⤵")
            return await vc.play(TrackObject)

    @commands.command(aliases=["stop", "ause"])
    async def pause(
        self,
        ctx,
        delay: int
        | None = param(
            description="\n    (opt.) [int] The amount of time to delay for, in seconds.",
            default=None,
            displayed_default=None,
        ),
    ):
        """\n    Pauses the currently playing track, optionally with a timer."""

        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        if vc:
            current_timestamp = round(math.floor(vc.position / 1000))
            duration_timestamp = round(math.floor(vc.current.length / 1000))

            message = await ctx.reply(
                f"⏸ PAUSED | `{vc.current}` by **{vc.current.author}** [{craft.formatted_time(current_timestamp)} / {craft.formatted_time(duration_timestamp)}]"
            )
            await vc.pause()
            try:
                if delay:
                    await message.edit(
                        f"{message.content}\n\n⏯ Paused for {delay} seconds..."
                    )
                    asyncio.sleep(int(delay))
                    await message.edit(
                        f"{message.content}\n\n⏯ Resumed after {delay} seconds."
                    )
                    vc.resume()
            except:
                pass
        else:
            return await ctx.reply("❌ There's nothing to pause!")

    @commands.command(aliases=["leave", "dc"])
    async def disconnect(self, ctx):
        """\n    Disconnects from the connected VC."""
        vc: wavelink.Player = ctx.voice_client

        if vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        if vc:
            vc.cleanup()
            await vc.disconnect()
            return await ctx.message.add_reaction("👋")
        else:
            await ctx.message.add_reaction("👻")

    def get_nowplaying(self, vc: wavelink.Player) -> str:
        if vc.current:
            current_timestamp = round(math.floor(vc.position / 1000))
            duration_timestamp = round(math.floor(vc.current.length / 1000))
        else:
            current_timestamp = None
            duration_timestamp = None

        now_playing = f"▶ Now Playing: `{vc.current if vc.current else 'Unknown'}` by **{vc.current.author if vc.current else 'Unknown'}** [{craft.formatted_time(current_timestamp) if current_timestamp else '0:00'} / {craft.formatted_time(duration_timestamp) if duration_timestamp else '0:00'}]"
        return now_playing

    async def display_message(self, ctx=None, vc: wavelink.Player = None) -> None:
        now_playing = self.get_nowplaying(vc)

        track = vc.current

        async with aiohttp.ClientSession() as session:
            thumb_url = track.thumbnail or await track.fetch_thumbnail()

            file = await craft.file_from_url(thumb_url, session) if thumb_url else None
            if ctx:
                await ctx.reply(
                    content=now_playing,
                    file=file,
                )
            elif self.preferred_channel[2]:
                await self.preferred_channel[0].send(
                    content=now_playing,
                    file=file,
                )

    @commands.command(aliases=["np", "current", "nowplaying"])
    async def now_playing(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if vc:
            return await self.display_message(ctx, vc)
        return await ctx.message.add_reaction("❌")

    @commands.command(aliases=["q", "list", "playlist"])
    async def queue(
        self,
        ctx,
        page_number: int
        | None = param(
            description="\n    (opt.) [int] {1-MAX} The page number of the queue to display.",
            default=1,
            displayed_default=None,
        ),
    ):
        """\n    Displays currently playing song and the queue. For more info on the current song, use the `nowplaying` command."""
        vc: wavelink.Player = ctx.voice_client
        if not vc or (len(vc.queue) == 0 and not vc.current):
            return await ctx.reply("There is no queue!")

        now_playing = f"{self.get_nowplaying(vc)}\n----------\n"
        if len(vc.queue) > 1:
            full_queue = [
                f"[#{i+1}] `{vc.queue[i]}` by **{vc.queue[i].author}** [{craft.formatted_time(round(math.floor(vc.queue[i].length / 1000)))}]"
                for i in range(len(vc.queue))
            ]

            queue_pages = [
                full_queue[x : x + 10] for x in range(0, len(full_queue), 10)
            ]

            if page_number > len(queue_pages):
                page_number = len(queue_pages)
            elif page_number <= 0:
                page_number = 1
            queue_content = "\n".join(queue_pages[page_number - 1])
        else:
            queue_content = ""
            page_number = "0"
            queue_pages = ""

        await ctx.reply(
            f"```Queue```----------\n{now_playing}{queue_content}\n\n*Page {page_number} of {len(queue_pages)}*"
        )

    @commands.command(aliases=["r", "c", "remove", "cut"])
    async def clear(
        self,
        ctx,
        entry: str
        | None = param(
            description="\n    [int/string] {1-MAX} The queue entry to remove. Could either be an entry number or keyword.\n     --> KEYWORDS: [all/start/end]",
            default=None,
            displayed_default=None,
        ),
    ):
        """\n    Removes the given track entry number, if possible. Does NOT skip the currently playing track."""
        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        if vc:
            if not entry:
                return await ctx.reply(
                    "- You can remove either [all] the tracks, the [start] or [end] of the queue, or any [entry number] on the queue."
                )
            match (entry.lower()):
                case "all" | "queue" | "q":
                    await ctx.reply(f"📃 Clearing queue.")
                    return vc.queue.clear()
                case "start" | "beginning" | "begin" | "first" | "top":
                    track = vc.queue.get()
                case "end" | "last" | "bottom":
                    track = vc.queue.pop()
                case _:
                    try:
                        index = int(entry)
                        track = vc.queue[index - 1]
                        del vc.queue[index - 1]
                    except ValueError:
                        return await ctx.reply("❌ Please provide a valid entry number!")

            return await ctx.reply(f"🗑 Removed `{track}` by **{track.author}**.")
        await ctx.message.add_reaction("❌")

    @commands.command(aliases=["next", "pass", "s"])
    async def skip(self, ctx):
        """\n    Skips the currently playing song, if possible."""
        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        if vc:
            await ctx.reply("⏭ Skipping song...")
            return await vc.seek(vc.current.length)
        await ctx.message.add_reaction("❌")

    @commands.command(aliases=["repeat", "l"])
    async def loop(
        self,
        ctx,
        mode: str
        | None = param(
            description="\n    [str] {one/all/both/none} The mode to adjust. See p!help loop for more info.",
            default=None,
            displayed_default=None,
        ),
        value: str
        | None = param(
            description="\n    (opt.) {true/false} The value to set the mode to. Otherwise toggles the option.",
            default=None,
            displayed_default=None,
        ),
    ):
        """\n    Displays or changes the loop settings for the bot.

        Mode "one" repeats the currently playing track.
        Mode "all" repeats the queue.
        Mode "both" is a shorthand taht sets both settings to true.
        Mode "none" is a shorthand that sets both settings to false.

        The modes are non-mutually exclusive; mode "one" will take precedence over "all".
        """
        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        if vc:
            if not mode:
                mode = "placeholder"
            match (mode.lower()):
                case "one" | "track":
                    vc.queue.loop = (
                        True
                        if value == "true"
                        else False
                        if value == "false"
                        else not vc.queue.loop
                    )
                case "all" | "queue":
                    vc.queue.loop_all = (
                        True
                        if value == "true"
                        else False
                        if value == "false"
                        else not vc.queue.loop_all
                    )
                case "both":
                    vc.queue.loop = True
                    vc.queue.loop_all = True
                case "none":
                    vc.queue.loop = False
                    vc.queue.loop_all = False
                case _:
                    return await ctx.reply(
                        f"```🔃 Loop settings```\n- Loop track: `{vc.queue.loop}`\n- Loop all: `{vc.queue.loop_all}`"
                    )
            return await ctx.reply(
                f"Your loop settings have changed.\n\n- Loop track: `{vc.queue.loop}`\n- Loop all: `{vc.queue.loop_all}`"
            )
        else:
            await ctx.message.add_reaction("🤫")

    @commands.command(aliases=["goto", "gt"])
    async def seek(
        self,
        ctx,
        timestamp: str
        | None = param(
            description="\n    [str/int] {matches format: HH:MM:SS/##h##m##s/##} The timestamp to seek to. If format is ##, it will be checked as seconds.",
            default=None,
            displayed_default=None,
        ),
    ):
        """\n    Seeks the currently playing track to the given timestamp, if possible."""
        vc: wavelink.Player = ctx.voice_client

        if not ctx.author.voice:
            return await ctx.reply(
                "🤓 Hey silly! You have to be in a VC to use the music bot :P"
            )
        elif vc and (
            ctx.author.voice.channel != vc.channel and len(vc.channel.members) >= 2
        ):
            return await ctx.reply(
                f"❌ The bot is currently in use, please join me in {vc.channel.mention} instead!"
            )

        if vc and vc.current:
            if not timestamp:
                return await ctx.reply("❌ No timestamp provided!")
            try:
                match (timestamp):
                    case "start" | "beginning" | "begin":
                        timestamp = "0"
                    case "middle":
                        timestamp = f"{vc.current.length/2}"
                    case "end":
                        timestamp = f"{vc.current.length}"
                    case _:
                        timestamp = timestamp

                text = list(filter(None, re.split("h|m|s|:", timestamp)))
                seconds = sum(
                    [
                        a * b
                        for a, b in zip(
                            [3600, 60, 1][(-1 * len(text)) + 3 :], map(int, text)
                        )
                    ]
                )
                await ctx.reply(f"⏭ Seeking to {craft.formatted_time(seconds)}...")
                return await vc.seek(seconds * 1000)
            except Exception as exc:
                await ctx.reply(
                    f"There was an error in trying to seek to your given timestamp: {exc}"
                )

        await ctx.message.add_reaction("❌")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackEventPayload):
        track = payload.original
        player = payload.player
        return await self.display_message(None, player)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        try:
            next_song: wavelink.Playable = payload.player.queue.get()
            if next_song:
                await payload.player.play(next_song)
        except wavelink.exceptions.QueueEmpty:
            if self.preferred_channel[2]:
                return await self.preferred_channel[0].send("⏹ Queue ended!")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and not after.channel:
            self.preferred_channel = [None, False, True]

    async def cog_command_error(self, ctx, error):
        if type(error) == commands.CheckFailure:
            return await ctx.reply(
                file=craft.file_from_url(
                    "https://media.discordapp.net/attachments/1131772558530859028/1132432711156514826/image.png?"
                )
            )
        elif type(error) == commands.CommandOnCooldown:
            return await ctx.reply(
                f"❌ The command is on cooldown! Please try again {discord.utils.format_dt(discord.utils.utcnow() + datetime.timedelta(seconds=error.retry_after), 'R')}!"
            )
        await ctx.reply(
            f"❌ Error occurred. <@{self.bot.owner_id}>\nInvocation Context: `{ctx.message.content}`\nError: `{error}`\n\n*This feature is still in development. Please forward all suggestions/bug reports to <@{self.bot.owner_id}>!*"
        )

    async def query_tracks(self, ctx, mode, search):
        try:
            match (mode.lower()):
                case "yt" | "youtube":
                    try:
                        if "playlist" in search:
                            yt_playlist: wavelink.YouTubePlaylist = (
                                await wavelink.YouTubePlaylist.search(search)
                            )

                            return yt_playlist
                    except:
                        pass

                    yt_tracks: list[
                        wavelink.YouTubeTrack
                    ] = await wavelink.YouTubeTrack.search(search)

                    if yt_tracks:
                        return yt_tracks[0]
                    return False
                case "soundcloud" | "sc":
                    try:
                        if "sets" in search:
                            sc_playlist: list[
                                wavelink.SoundCloudPlaylist
                            ] = await wavelink.SoundCloudPlaylist.search(search)
                            if sc_playlist:
                                return sc_playlist
                    except Exception as exc:
                        pass
                    sc_tracks: list[
                        wavelink.SoundCloudTrack
                    ] = await wavelink.SoundCloudTrack.search(search)

                    if sc_tracks:
                        return sc_tracks[0]
                    return False
                case "spt" | "spotify":
                    sptfy_playlist = list[spotify.SpotifyTrack] = None
                    sptfy_tracks = list[spotify.SpotifyTrack] = None

                    return []
                case "direct_mode":
                    tracks: list[
                        wavelink.GenericTrack
                    ] = await wavelink.GenericTrack.search(search)
                    if tracks:
                        return tracks[0]
                    return False
        except Exception as exc:
            await ctx.reply(f"general error: {exc}")
            return False

    @commands.command(aliases=["diff", "calc", "fe2"])
    async def calculate_difficulty(
        self,
        ctx,
        current_difficulty=param(
            description="\n    [1.0 - 5.99] The actual difficulty rating, listed above the boost button",
            default=None,
            displayed_default=None,
        ),
        players_survived=param(
            description="\n    (opt.) [0-16] Number of surviving players OR none if players_total is a decimal",
            default=None,
            displayed_default=None,
        ),
        players_total=param(
            description="\n    [1-16 / 1-16] The total amount of players in the round OR decimal % of survivors",
            default=None,
            displayed_default=None,
        ),
        intensity_2x=param(
            description="\n    {0-3} Boosts with 2x intensity boosting. 3 is only possible if intensity_1x is 0",
            default=None,
            displayed_default=None,
        ),
        intensity_1x=param(
            description="\n    {0-5} Boosts with 1x intensity boosting. 4+ is only possible if intensity_2x is 0",
            default=None,
            displayed_default=None,
        ),
    ):
        """\n    Caluclates the minimum, maximum, and probable intensities of the next FE2 round.

        The base minimum difficulty without boosts can be calucated with setting both intensity boosts to 0.

        2x Intensity Boost Gamepass users can be checked if the new minimum intensity is (base minimum difficulty + 1.0).
        """
        try:
            if not intensity_1x and (
                not current_difficulty
                or not players_survived
                or not players_total
                or not intensity_2x
            ):
                raise Exception("One of the values is not correct")
            elif not intensity_1x:
                player_percentage = float(players_survived)
                intensity_1x = int(intensity_2x)
                intensity_2x = int(players_total)
                players_total = None
            else:
                player_percentage = None
                intensity_1x = int(intensity_1x)
                intensity_2x = int(intensity_2x)
                players_total = int(players_total)

            current_difficulty = float(current_difficulty)

            base_difficulty = math.floor(current_difficulty)

            match (base_difficulty):
                case 1:
                    difficulty = 0.4
                case 2:
                    difficulty = 0.5
                case 3:
                    difficulty = 0.6
                case 4:
                    difficulty = 0.65
                case 5:
                    difficulty = 1.5

            if (
                (2 * intensity_2x) + intensity_1x > 5
                or intensity_2x < 0
                or intensity_1x < 0
            ):
                raise Exception(
                    "Amount of boosts are either grearer than maximum of 5 'stacks' or below minimum of 0 'stacks'."
                )
            elif intensity_2x > 3:
                raise Exception("Amount of 2x intensity boosts are too high.")

            intensity_1x = int(intensity_1x) * 0.5

            if not player_percentage:
                player_percentage = round(int(players_survived) / int(players_total), 2)

            if player_percentage > 1:
                raise Exception("Players survived greater than players total")

            intensity_boost = int(intensity_2x) + intensity_1x

            intensity_change = lambda x, y, z: x - y + z

            min_diff = current_difficulty + intensity_change(
                0, difficulty, intensity_boost
            )
            max_diff = current_difficulty + intensity_change(
                1, difficulty, intensity_boost
            )
            prob_diff = current_difficulty + intensity_change(
                player_percentage,
                difficulty,
                intensity_boost,
            )

            if players_total:
                value_of_one_player = 1 / players_total

                staying_difference = base_difficulty - min_diff

                required_players = round(
                    math.ceil(staying_difference / value_of_one_player), 2
                )

                if required_players < 0:
                    required_players = 0
                elif required_players > players_total:
                    required_players = "IMPOSSIBLE | round will drop in difficulty"

                if base_difficulty == 5:
                    required_players_up = "IMPOSSIBLE | max difficulty reached"
                else:
                    increasing_difference = (
                        base_difficulty + 1 if base_difficulty < 5 else 0
                    ) - min_diff

                    required_players_up = round(
                        math.ceil(increasing_difference / value_of_one_player), 2
                    )

                    if required_players_up < 0:
                        required_players_up = 0
                    elif required_players_up > players_total:
                        required_players_up = "IMPOSSIBLE | round will stay at or drop below current difficulty"
            else:
                required_players = "IMPOSSIBLE | total amount of players not given"
                required_players_up = "IMPOSSIBLE | total amount of players not given"

            return await ctx.reply(
                f"*Minimum Difficulty: {min_diff}*\n*Maximum Difficulty: {max_diff}*\n**Probable Difficulty:** `{prob_diff}`\n__Players needed to survive to keep difficulty:__ `{required_players}`\n__Players needed to survive to increase difficulty:__ `{required_players_up}`"
            )
        except Exception as exc:
            traceback.print_exception(exc)
            return await ctx.reply(
                f"One or more arguments are invalid. Please try again | {exc}"
            )


async def setup(bot):
    print(f'> Loading cog "extensions.{name}"...')
    await bot.add_cog(Cog(bot), override=True)


async def teardown(bot):
    print(f'> Unloading cog "extensions.{name}"...')
    await bot.remove_cog(name)
