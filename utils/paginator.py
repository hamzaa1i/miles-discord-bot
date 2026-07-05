"""utils/paginator.py — reusable pagination View for multi-page embeds.

Usage:
    from utils.paginator import Paginator

    pages = [embed1, embed2, embed3]
    view = Paginator(pages)
    await interaction.response.send_message(embed=pages[0], view=view)
"""
import discord
from typing import List


class Paginator(discord.ui.View):
    def __init__(self, pages: List[discord.Embed], timeout: int = 60):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current >= len(self.pages) - 1
        self.counter.label = f"{self.current + 1}/{len(self.pages)}"

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current > 0:
            self.current -= 1
            self._update_buttons()
        try:
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except Exception:
            pass

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            self._update_buttons()
        try:
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)
        except (discord.NotFound, discord.InteractionResponded):
            pass
        except Exception:
            pass

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass
