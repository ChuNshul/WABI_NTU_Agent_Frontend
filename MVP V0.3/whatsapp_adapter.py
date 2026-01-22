from typing import Dict, Any, List

def convert_web_to_whatsapp(web_ui_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapter Pattern: Converts a Rich Web UI Plan into a WhatsApp-compatible payload.
    Downgrades complex UI components to Text/List/Button representations.
    """
    messages = []
    
    # 1. Summary -> Simple Text Message
    if web_ui_plan.get("summary"):
        messages.append({
            "type": "text", 
            "body": web_ui_plan["summary"]
        })

    # 2. Process Sections
    for section in web_ui_plan.get("sections", []):
        msg = _convert_section(section)
        if msg:
            messages.append(msg)

    # 3. Suggestions -> Interactive Buttons (Limit 3)
    suggestions = web_ui_plan.get("suggestions", [])
    if suggestions:
        buttons = [
            {"type": "reply", "reply": {"id": f"btn_{i}", "title": txt[:20]}} 
            for i, txt in enumerate(suggestions[:3])
        ]
        messages.append({
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "What would you like to do next?"},
                "action": {"buttons": buttons}
            }
        })

    return {"messages": messages}

def _convert_section(section: Dict[str, Any]) -> Dict[str, Any]:
    """Converts individual UI sections to WhatsApp format."""
    s_type = section.get("type")
    
    if s_type == "text":
        return {"type": "text", "body": section["content"]}
        
    elif s_type == "carousel":
        # Web Carousel -> WhatsApp Formatted Text List
        # (WhatsApp List Messages are complex to implement in MVP, so we use formatted text)
        lines = [f"*{section.get('title', 'Options')}*"]
        for item in section.get("items", []):
            lines.append(f"📍 *{item['title']}*")
            lines.append(f"_{item['subtitle']}_")
            if item.get("details", {}).get("restaurant", {}).get("rating"):
                lines.append(f"⭐ {item['details']['restaurant']['rating']}")
            lines.append("") # spacer
            
        return {"type": "text", "body": "\n".join(lines)}
        
    elif s_type == "key_value_list":
        # Web Table -> WhatsApp Key-Value Text
        lines = [f"*{section.get('title', 'Details')}*"]
        for item in section.get("items", []):
            icon = "✅" if item.get("highlight") is True else ("⚠️" if item.get("highlight") is False else "🔸")
            lines.append(f"{icon} {item['label']}: {item['value']}")
            
        return {"type": "text", "body": "\n".join(lines)}
        
    elif s_type == "highlight_box":
        # Web Box -> WhatsApp Bold Text with Emoji
        variant = section.get("variant", "info")
        icon = "🟢" if variant == "success" else ("🔴" if variant == "warning" else "ℹ️")
        return {"type": "text", "body": f"{icon} *{section['content']}*"}
        
    elif s_type == "image_display":
        # Web Image -> WhatsApp Image Message (Placeholder logic)
        return {
            "type": "text", 
            "body": f"📷 [Image: {section.get('caption', 'Food Image')}]"
        }
        
    return None