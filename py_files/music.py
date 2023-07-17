from discord.ext import commands
import discord
import os
import wavelink
from wavelink.ext import spotify
from utilities import craft
import aiohttp
import math
import asyncio

name = (os.path.basename(__file__)).replace(".py", "")


class Cog(commands.Cog, name=name):
    def __init__(self, bot):
        self.bot = bot
        self.preferred_channel = None

    async def cog_after_invoke(self, ctx):
        self.preferred_channel = ctx.channel

    @commands.command(
        aliases=[
            "p",
            "start",
            "connect",
            "join",
            "continue",
            "resume",
            "switch",
            "move",
            "lay",
            "search",
        ]
    )
    async def play(
        self,
        ctx,
        channel: discord.VoiceChannel | None = None,
        mode: str | None = None,
        *,
        search: str | None = None,
    ) -> None:
        """[channel (opt)] [source (opt)] [search (opt)] | Joins a VC and plays a song, if possible. Otherwise resumes a paused song.


        channel: A specific channel you want the bot to join. If invalid, it will try to join your current voice channel.
        source: changes whether it searches from Youtube (yt), SoundCloud (sc), Spotify (spt) or "direct_mode". Direct Mode is basically playing from a link directly.
        search: The phrase to search on Youtube.


        Playlists are checked for first - if it's not a playlist, then it will use your search select method.
        """
        if search is None:
            search = mode
            mode = "youtube"
        else:
            mode = mode.lower()
        message = None

        try:
            channel = channel or ctx.author.voice.channel

            if not ctx.voice_client:
                message = await ctx.reply(f"✔ Joining `{channel.name}`...")
                vc: wavelink.Player = await channel.connect(
                    cls=wavelink.Player, self_deaf=True
                )
            else:
                vc: wavelink.Player = ctx.voice_client
                if channel and vc.channel != channel:
                    message = await ctx.reply(f"➡ Switching to `{channel.name}`...")
                    await vc.move_to(channel)
        except AttributeError as exc:
            await ctx.reply(exc)
            return await ctx.reply(
                "🤓 Hey, silly! Provide a voice channel or be in one so I know which one to join!"
            )
        except Exception as exc:
            return await ctx.reply(f"❌ An error occurred: {exc}")

        # Resume
        if search is None:
            if vc.is_paused():
                message = (
                    await ctx.reply("✅ Resuming...")
                    if not message
                    else await message.edit(
                        content=f"{message.content}\n\n✅ Resuming..."
                    )
                )
                return await vc.resume()
            elif ctx.invoked_with in ["resume", "continue"]:
                if not vc.is_playing():
                    message = (
                        await ctx.reply("❌ There is no track to resume!")
                        if not message
                        else await message.edit(
                            content=f"{message.content}\n\n❌ There is no track to resume!"
                        )
                    )
                    return
                else:
                    message = (
                        await ctx.reply("▶ The track's already playing, bud!")
                        if not message
                        else await message.edit(
                            content=f"{message.content}\n\n▶ The track's already playing, bud!"
                        )
                    )
                    return
            else:
                message = (
                    await ctx.reply("❓ Whatcha wanna play?")
                    if not message
                    else await message.edit(
                        content=f"{message.content}\n\n❓ Whatcha wanna play?"
                    )
                )
                return

        # Playing/Queuing
        message = (
            await ctx.reply("⏳ Loading...")
            if not message
            else await message.edit(content=f"{message.content}\n\n⏳ Loading...")
        )

        ## QUEUING
        if "spotify.com" in search:
            mode = "spt"
        elif "soundcloud.com" in search:
            mode = "sc"

        try:
            TrackObject = await self.query_tracks(mode, search)
        except:
            return await message.edit(
                content=f"{message.content}\n\n❌ Something wrong happened! Could not complete search.\n\n*This feature is in beta. Send all suggestions to @issu*"
            )

        if type(TrackObject) == list:
            return await message.edit(
                f"{message.content}\n\nSpotify tracks/playlists are currently not supported. Sorry!"
            )
        elif TrackObject is False:
            return await message.edit(
                content=f"{message.content}\n\n❌ Could not find your desired song, even with all the different searches!\n\n*This feature is in beta. Send all suggestions to @issu*"
            )

        if (
            type(TrackObject) == wavelink.YouTubePlaylist
            or type(TrackObject) == wavelink.SoundCloudPlaylist
        ):
            await message.edit(
                content=f"{message.content}\n\n📃 Queued `{TrackObject}` starting at __Position #{len(vc.queue)}__"
            )
            await vc.queue.put_wait(TrackObject)
            return await vc.play(vc.queue.get())

        if vc.is_playing():
            await message.edit(
                content=f"{message.content}\n\n📃 Queued `{TrackObject}` by **{TrackObject.author}** at __Position #{len(vc.queue)}__"
            )
            return await vc.queue.put(TrackObject)
        else:
            await message.edit(content=f"{message.content}\n\nNow playing! ⤵")
            return await vc.play(TrackObject)

    @commands.command(aliases=["stop", "ause"])
    async def pause(self, ctx, delay: int | None = None):
        """Pauses the currently playing track, optionally with a timer.

        delay (opt.) - Time in seconds to pause the track.
        """

        vc: wavelink.Player = ctx.voice_client

        if vc:
            current_timestamp = round(math.floor(vc.position / 1000))
            duration_timestamp = round(math.floor(vc.current.length / 1000))

            await ctx.reply(
                f"⏸ PAUSED | `{vc.current}` by **{vc.current.author}** [{craft.formatted_time(current_timestamp)} / {craft.formatted_time(duration_timestamp)}]"
            )
            await vc.pause()
            if delay:
                asyncio.sleep(delay)
                await ctx.reply("▶ Resumed after {delay} seconds.")
                vc.resume()

    @commands.command(aliases=["leave", "dc"])
    async def disconnect(self, ctx) -> None:
        """Disconnects from the connected VC.

        This command assumes there is a currently connected Player.
        """
        vc: wavelink.Player = ctx.voice_client

        if vc:
            vc.cleanup()
            await vc.disconnect()
            return await ctx.message.add_reaction("👋")
        else:
            await ctx.message.add_reaction("👻")

    @commands.command(aliases=["q", "list", "playlist", "np", "nowplaying", "current"])
    async def queue(self, ctx, page_number: int | None = 1):
        """Displays currently playing song and the queue.

        In a future update, nowplaying will be its own command.
        """
        vc: wavelink.Player = ctx.voice_client
        if not vc or len(vc.queue) == 0:
            return await ctx.reply("There is no queue!")

        if vc.current:
            current_timestamp = round(math.floor(vc.position / 1000))
            duration_timestamp = round(math.floor(vc.current.length / 1000))
        else:
            current_timestamp = 0000
            duration_timestamp = 0000

        now_playing = f"▶ Now Playing: `{vc.current}` by **{vc.current.author if vc.current else 'Unknown'}** [{craft.formatted_time(current_timestamp)} / {craft.formatted_time(duration_timestamp)}]\n----------\n"

        full_queue = [
            f"[#{i+1}] `{vc.queue[i]}` by **{vc.queue[i].author}** [{craft.formatted_time(round(math.floor(vc.queue[i].length / 1000)))}]"
            for i in range(len(vc.queue))
        ]

        queue_pages = [full_queue[x : x + 10] for x in range(0, len(full_queue), 10)]

        queue_content = "\n".join(queue_pages[page_number - 1])

        await ctx.reply(
            f"```Queue```----------\n{now_playing}{queue_content}\n\n*Page {page_number} of {len(queue_pages)}*"
        )

    @commands.command(aliases=["empty", "cq"])
    async def clear(self, ctx):
        """Clears the entire queue. Does not skip currently playing songs, if any."""
        vc: wavelink.Player = ctx.voice_client
        if vc:
            await ctx.reply(f"Clearing queue.")
            vc.queue.clear()

        else:
            ctx.message.add_reaction("❌")

    @commands.command(aliases=["next", "pass"])
    async def skip(self, ctx):
        """Skips the currently playing song, if possible."""
        vc: wavelink.Player = ctx.voice_client
        if vc:
            await ctx.reply("⏭ Skipping song...")
            await vc.seek(vc.current.length)
        else:
            await ctx.message.add_reaction("❌")

    @commands.command(aliases=["repeat"])
    async def loop(self, ctx, mode: str | None = None, value: str | None = None):
        """[mode (opt)] [value (opt)] | Changes the loop settings for the bot.

        mode: the mode to adjust. Valid settings: {one} | {all} | {none}
        value: the value for the mode. Valid settings: {true} | {false}

        Mode "one" repeats the currently playing track.
        Mode "all" repeats the queue.
        Mode "none" is a shorthand that sets both settings to false.

        The modes are non-mutually exclusive; mode "one" will take precedence over "all".
        """
        vc: wavelink.Player = ctx.voice_client
        if vc:
            if not mode or not value:
                await ctx.reply(
                    f"```🔃 Loop settings```\n- Loop track: `{vc.queue.loop}`\n- Loop all: `{vc.queue.loop_all}`"
                )
            else:
                match (mode.lower()):
                    case "one" | "track":
                        vc.queue.loop = True if value == "true" else False if value == "false" else vc.queue.loop
                    case "all" | "queue":
                        vc.queue.loop_all = True if value == "true" else False if value == "false" else vc.queue.loop_all
                    case "none":
                        vc.queue.loop = False
                        vc.queue.loop_all = False
                    case _:
                        return await ctx.reply("So what are you setting that to?")

                return await ctx.reply(
                    f"Your loop settings have changed.\n\n- Loop track: `{vc.queue.loop}`\n- Loop all: `{vc.queue.loop_all}`"
                )

        else:
            ctx.message.add_reaction("🤫")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        async with aiohttp.ClientSession() as session:
            thumb_url = (
                payload.original.thumb
                if payload.original.thumb
                else await payload.original.fetch_thumbnail()
            )
            file = await craft.file_from_url(thumb_url, session) if thumb_url else None
            await self.preferred_channel.send(
                content=f"▶ Now Playing: `{payload.track}` by **{payload.track.author}**",
                file=file,
            )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        try:
            next_song: wavelink.Playable = payload.player.queue.get()
            if next_song:
                await payload.player.play(next_song)
        except wavelink.exceptions.QueueEmpty:
            return await self.preferred_channel.send("⏹ Queue ended!")

    async def cog_command_error(self, ctx, error):
        await ctx.send(
            f"Error occurred. <@{self.bot.owner_id}>\nInvocation Context: `{ctx.message.content}`\nError: `{error}`\n\n*This feature is still in development. Please forward all suggestions/bug reports to <@{self.bot.owner_id}>!*"
        )

    async def query_tracks(self, mode, search):
        try:
            match (mode.lower()):
                case "yt" | "youtube":
                    yt_playlist: wavelink.YouTubePlaylist = (
                        await wavelink.YouTubePlaylist.search(search)
                    )
                    yt_tracks: list[
                        wavelink.YouTubeTrack
                    ] = await wavelink.YouTubeTrack.search(search)

                    if yt_playlist:
                        return yt_playlist
                    elif yt_tracks:
                        return yt_tracks[0]
                    return False
                case "soundcloud" | "sc":
                    sc_playlist: list[
                        wavelink.SoundCloudPlaylist
                    ] = await wavelink.SoundCloudPlaylist()
                    sc_tracks: list[
                        wavelink.SoundCloudTrack
                    ] = await wavelink.SoundCloudTrack.search(search)
                    if sc_playlist:
                        return sc_playlist[0]
                    elif sc_tracks:
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
            print(exc)
            return False


async def setup(bot):
    print(f'> Loading cog "extensions.{name}"...')
    await bot.add_cog(Cog(bot), override=True)


async def teardown(bot):
    print(f'> Unloading cog "extensions.{name}"...')
    await bot.remove_cog(name)
