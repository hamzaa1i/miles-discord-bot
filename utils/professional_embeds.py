import discord
from datetime import datetime

def create_professional_embed(title="", description="", color=discord.Color.blue(), **kwargs):
    """Create a professional embed with minimal styling"""
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

def success_embed(title, description):
    """Professional success message"""
    return create_professional_embed(
        title=f"✓ {title}",
        description=description,
        color=discord.Color.green()
    )

def error_embed(title, description):
    """Professional error message"""
    return create_professional_embed(
        title=f"✗ {title}",
        description=description,
        color=discord.Color.red()
    )

def info_embed(title, description):
    """Professional info message"""
    return create_professional_embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )

def warning_embed(title, description):
    """Professional warning message"""
    return create_professional_embed(
        title=f"⚠ {title}",
        description=description,
        color=discord.Color.orange()
    )