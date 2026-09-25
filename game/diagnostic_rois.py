"""Named scanner ROI groups shared by diagnostics and overlays."""

ROI_GROUPS = {
    "inventory-weapons": (
        ("count", "weapons.page"),
        ("grid-first", "weapons.start"),
        ("name", "weapons.name"),
        ("quantity", "weapons.value"),
        ("level", "weapons.level"),
        ("rank", "weapons.rank"),
    ),
    "inventory-echoes": (
        ("count", "echoes.page"),
        ("grid-first", "echoes.start"),
        ("card", "echoes.echoCard"),
        ("sonata", "echoes.sonata"),
        ("stats-name", "echoes.fullStatsName"),
        ("stats-value", "echoes.fullStatsValue"),
    ),
    "inventory-items": (
        ("grid-first", "items.start"),
        ("info", "items.info"),
        ("description", "items.description"),
    ),
    "resonator-overview": (
        ("name", "characters.resonatorName"),
        ("level", "characters.resonatorLevel"),
    ),
    "resonator-weapon": (
        ("name", "characters.weaponName"),
        ("level", "characters.weaponLevel"),
        ("rank", "characters.weaponRank"),
    ),
    "resonator-skills": (
        ("level", "characters.skillLevel"),
        ("button", "characters.skillButton"),
    ),
    "resonator-chain": (
        ("button", "characters.chainButton"),
    ),
    "achievements": (
        ("status", "achievements.status"),
    ),
    "shell-credit": (
        ("shell", "shell"),
    ),
    "main-menu": (
        ("terminal", "terminal"),
    ),
}
