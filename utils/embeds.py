import discord
from datetime import datetime

def create_embed(title="", description="", color=discord.Color.blue(), **kwargs):
    """Create a standard embed with consistent styling"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    
    # Add optional fields
    for key, value in kwargs.items():
        if hasattr(embed, f'set_{key}'):
            getattr(embed, f'set_{key}')(value)
    
    return embed

def error_embed(message):
    """Create error embed"""
    return create_embed(
        title="❌ Error",
        description=message,
        color=discord.Color.red()
    )

def success_embed(message):
    """Create success embed"""
    return create_embed(
        title="✅ Success",
        description=message,
        color=discord.Color.green()
    )

def info_embed(message):
    """Create info embed"""
    return create_embed(
        title="ℹ️ Information",
        description=message,
        color=discord.Color.blue()
    )