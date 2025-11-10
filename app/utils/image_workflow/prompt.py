CATEGORIES = {
    "Top": """
Use the provided full-body photo as reference. Extract and isolate only the top.
Preserve original silhouette, proportions, fabric texture, and colors. Remove the person completely.

Output a clean, standalone top with:
• Solid contrasting studio background (choose a color that makes the top stand out)
• High-fidelity photorealistic detail
• Crisp edges, natural shape, realistic folds
• Enhanced fabric clarity and lighting
• Soft natural shadow below for depth
• No distortion, no flattening, no mannequin, no hanger
• No body parts, no face, no arms, no neck, no hands
• No additional props, no flooring, no accessories

Goal: fashion e-commerce catalog quality - floating garment on a clean solid contrasting background.
""",
    "Bot": """
Use the provided full-body photo as reference. Extract and isolate only the pants/trousers.
Preserve original silhouette, proportions, fabric texture, and colors. Remove the person completely.

Output a clean, standalone bottom with:
• Solid contrasting studio background (choose a color that makes the pants stand out)
• High-fidelity photorealistic detail
• Crisp edges, natural shape, realistic folds
• Enhanced fabric clarity and lighting
• Soft natural shadow below for depth
• No distortion, no flattening, no mannequin, no hanger
• No body parts, no torso, no feet, no shoes
• No additional props, no flooring, no accessories

Goal: fashion e-commerce catalog quality - floating garment on a clean solid contrasting background.
"""
}
