TREATMENTS = {
    "Apple Scab Leaf": {
        "cause": "Fungal - Venturia inaequalis. Spreads in wet cool conditions.",
        "severity": "medium",
        "chemical": [
            {"name": "Captan", "dose": "2g per litre", "interval": "Every 7-10 days"},
            {"name": "Myclobutanil", "dose": "1ml per litre", "interval": "At early signs"}
        ],
        "organic": [
            {"name": "Sulfur spray", "dose": "3g per litre", "interval": "Weekly in dry weather"},
            {"name": "Neem oil", "dose": "5ml per litre", "interval": "Weekly"}
        ],
        "prevention": "Prune infected branches. Avoid overhead watering. Remove fallen leaves.",
        "urgency_hours": 72
    },
    "Apple leaf": {
        "cause": "No disease detected. Leaf appears healthy.",
        "severity": "none",
        "chemical": [],
        "organic": [{"name": "Continue monitoring", "dose": "Weekly checks", "interval": "Weekly"}],
        "prevention": "Maintain proper irrigation and fertilization schedule.",
        "urgency_hours": 0
    },
    "Apple rust leaf": {
        "cause": "Fungal - Gymnosporangium species. Spreads from nearby juniper trees.",
        "severity": "high",
        "chemical": [
            {"name": "Propiconazole", "dose": "1ml per litre", "interval": "Before symptoms appear"},
            {"name": "Myclobutanil", "dose": "1ml per litre", "interval": "Every 10-14 days"}
        ],
        "organic": [
            {"name": "Copper fungicide", "dose": "2g per litre", "interval": "Early spring"}
        ],
        "prevention": "Remove nearby wild juniper bushes. Apply preventative sprays in early spring.",
        "urgency_hours": 48
    },
    "Bell_pepper leaf": {
        "cause": "No disease detected. Leaf appears healthy.",
        "severity": "none",
        "chemical": [],
        "organic": [{"name": "Continue monitoring", "dose": "Weekly checks", "interval": "Weekly"}],
        "prevention": "Ensure good soil drainage and proper spacing.",
        "urgency_hours": 0
    },
    "Bell_pepper leaf spot": {
        "cause": "Bacterial - Xanthomonas campestris. Thrives in warm, humid weather.",
        "severity": "high",
        "chemical": [
            {"name": "Copper hydroxide", "dose": "2.5g per litre", "interval": "Every 7 days"},
            {"name": "Mancozeb", "dose": "2g per litre", "interval": "Mixed with copper"}
        ],
        "organic": [
            {"name": "Copper soap", "dose": "Spray until dripping", "interval": "Every 7-10 days"}
        ],
        "prevention": "Use drip irrigation. Do not work in wet fields. Rotate crops.",
        "urgency_hours": 24
    },
    "Tomato Early blight leaf": {
        "cause": "Fungal - Alternaria solani. Starts on lower leaves during warm, wet weather.",
        "severity": "high",
        "chemical": [
            {"name": "Chlorothalonil", "dose": "2ml per litre", "interval": "Every 7 days"},
            {"name": "Mancozeb", "dose": "2g per litre", "interval": "Every 7-10 days"}
        ],
        "organic": [
            {"name": "Copper fungicide", "dose": "2g per litre", "interval": "Weekly"},
            {"name": "Bacillus subtilis", "dose": "Follow label", "interval": "Weekly preventative"}
        ],
        "prevention": "Stake plants for airflow. Apply mulch to prevent soil splashing.",
        "urgency_hours": 48
    },
    "Tomato Septoria leaf spot": {
        "cause": "Fungal - Septoria lycopersici. Spreads via splashing water.",
        "severity": "medium",
        "chemical": [
            {"name": "Chlorothalonil", "dose": "2ml per litre", "interval": "Every 7-10 days"}
        ],
        "organic": [
            {"name": "Copper soap", "dose": "Spray until wet", "interval": "Weekly"}
        ],
        "prevention": "Remove bottom leaves. Avoid overhead watering.",
        "urgency_hours": 72
    },
    "Tomato leaf": {
        "cause": "No disease detected. Leaf appears healthy.",
        "severity": "none",
        "chemical": [],
        "organic": [],
        "prevention": "Maintain consistent watering to prevent blossom end rot.",
        "urgency_hours": 0
    }
}

CLASS_NAMES = [
    "Apple Scab Leaf",
    "Apple leaf",
    "Apple rust leaf",
    "Bell_pepper leaf",
    "Bell_pepper leaf spot",
    "Blueberry leaf",
    "Cherry leaf",
    "Corn Gray leaf spot",
    "Corn leaf blight",
    "Corn rust leaf",
    "Peach leaf",
    "Potato leaf early blight",
    "Potato leaf late blight",
    "Raspberry leaf",
    "Soyabean leaf",
    "Squash Powdery mildew leaf",
    "Strawberry leaf",
    "Tomato Early blight leaf",
    "Tomato Septoria leaf spot",
    "Tomato leaf mold",
    "Tomato leaf",
    "Tomato leaf late blight",
    "Tomato leaf mosaic virus",
    "Tomato leaf yellow virus",
    "Tomato spider mite bug",
    "Grape leaf",
    "Grape leaf black rot"
]