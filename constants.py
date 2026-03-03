# constants.py - HELA SMART SACCO v3.0
# Color palette, theme presets, and color utility functions

from kivy.utils import get_color_from_hex

# ============================================================================
# VIBRANT COLOR PALETTE - Material Design 3
# ============================================================================

RAINBOW_COLORS = {
    # Primary Spectrum
    'primary': '#006C4C',
    'primary_light': '#4C9979',
    'primary_dark': '#004D36',
    'on_primary': '#FFFFFF',
    'primary_container': '#89F8C8',
    'on_primary_container': '#002114',

    # Secondary Spectrum (Purple-Blue)
    'secondary': '#6750A4',
    'secondary_light': '#9A82DB',
    'secondary_dark': '#4F378B',
    'on_secondary': '#FFFFFF',
    'secondary_container': '#E9DDFF',
    'on_secondary_container': '#21005D',

    # Tertiary Spectrum (Coral-Orange)
    'tertiary': '#984061',
    'tertiary_light': '#FFB0C8',
    'tertiary_dark': '#68002F',
    'on_tertiary': '#FFFFFF',
    'tertiary_container': '#FFD9E2',
    'on_tertiary_container': '#3E001D',

    # Quaternary (Teal-Cyan)
    'quaternary': '#006780',
    'quaternary_light': '#5DD5FC',
    'quaternary_dark': '#004D61',
    'quaternary_container': '#B8EAFF',

    # Quinary (Amber-Gold)
    'quinary': '#7D5700',
    'quinary_light': '#FFC94D',
    'quinary_dark': '#5A3F00',
    'quinary_container': '#FFE086',

    # Senary (Ruby-Red)
    'senary': '#9C4146',
    'senary_light': '#FFB3B6',
    'senary_dark': '#7A2B30',
    'senary_container': '#FFDAD9',

    # Septenary (Lime-Green)
    'septenary': '#3A6A1B',
    'septenary_light': '#A5D88C',
    'septenary_dark': '#204F00',
    'septenary_container': '#C2F2A6',

    # Octonary (Indigo)
    'octonary': '#3F51B5',
    'octonary_light': '#8C9EFF',
    'octonary_dark': '#002984',
    'octonary_container': '#C5CAE9',

    # Nonary (Deep Orange)
    'nonary': '#E65100',
    'nonary_light': '#FF9800',
    'nonary_dark': '#BF360C',
    'nonary_container': '#FFE0B2',

    # Denary (Pink-Magenta)
    'denary': '#C2185B',
    'denary_light': '#F48FB1',
    'denary_dark': '#880E4F',
    'denary_container': '#F8BBD0',

    # Undenary (Cyan-Aqua)
    'undenary': '#0097A7',
    'undenary_light': '#80DEEA',
    'undenary_dark': '#006064',
    'undenary_container': '#B2EBF2',

    # Duodenary (Deep Purple)
    'duodenary': '#512DA8',
    'duodenary_light': '#B39DDB',
    'duodenary_dark': '#311B92',
    'duodenary_container': '#D1C4E9',

    # Error Spectrum
    'error': '#B3261E',
    'error_light': '#F9DEDC',
    'error_dark': '#8C1D18',
    'on_error': '#FFFFFF',
    'error_container': '#F9DEDC',
    'on_error_container': '#410E0B',

    # Success Spectrum
    'success': '#2E7D32',
    'success_light': '#A5D6A7',
    'success_dark': '#1B5E20',
    'on_success': '#FFFFFF',
    'success_container': '#C8E6C9',
    'on_success_container': '#1B5E20',

    # Warning Spectrum
    'warning': '#F57C00',
    'warning_light': '#FFE0B2',
    'warning_dark': '#E65100',
    'on_warning': '#000000',
    'warning_container': '#FFF3E0',
    'on_warning_container': '#E65100',

    # Info Spectrum
    'info': '#1976D2',
    'info_light': '#BBDEFB',
    'info_dark': '#0D47A1',
    'on_info': '#FFFFFF',
    'info_container': '#E3F2FD',
    'on_info_container': '#0D47A1',

    # Neutral Spectrum
    'background': '#FFFBFE',
    'on_background': '#1C1B1F',
    'surface': '#FFFBFE',
    'on_surface': '#1C1B1F',
    'surface_variant': '#E7E0EC',
    'on_surface_variant': '#49454F',
    'outline': '#79747E',
    'outline_variant': '#CAC4D0',
    'shadow': '#000000',
    'scrim': '#000000',

    # Inverse Colors
    'inverse_surface': '#313033',
    'inverse_on_surface': '#F4EFF4',
    'inverse_primary': '#89F8C8',

    # Extended Colors
    'card_bg': '#FFFFFF',
    'card_elevated': '#F5F5F5',
    'divider': '#E0E0E0',
    'highlight': '#FF4081',
    'accent_blue': '#448AFF',
    'accent_green': '#69F0AE',
    'accent_yellow': '#FFFF00',
    'accent_purple': '#E040FB',
    'accent_cyan': '#18FFFF',
    'accent_orange': '#FFAB40',
    'gradient_start': '#667eea',
    'gradient_end': '#764ba2',

    # Dark Theme Colors
    'dark_background': '#1C1B1F',
    'dark_surface': '#313033',
    'dark_surface_variant': '#49454F',
    'dark_on_surface': '#E6E1E5',
}

# Theme presets
THEME_PRESETS = {
    'forest': {'primary': '#006C4C', 'secondary': '#6750A4', 'tertiary': '#984061'},
    'ocean': {'primary': '#006780', 'secondary': '#3F51B5', 'tertiary': '#0097A7'},
    'sunset': {'primary': '#E65100', 'secondary': '#C2185B', 'tertiary': '#7D5700'},
    'berry': {'primary': '#9C4146', 'secondary': '#512DA8', 'tertiary': '#C2185B'},
    'neon': {'primary': '#00E676', 'secondary': '#FF4081', 'tertiary': '#18FFFF'},
    'royal': {'primary': '#4A148C', 'secondary': '#FFD700', 'tertiary': '#C62828'},
}


def get_color(key: str, alpha: float = 1.0) -> tuple:
    """Get a color tuple from the palette with optional alpha."""
    hex_color = RAINBOW_COLORS.get(key, '#000000')
    r, g, b = get_color_from_hex(hex_color)[:3]
    return (r, g, b, alpha)


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple:
    """Convert a hex color string to an RGBA tuple."""
    r, g, b = get_color_from_hex(hex_color)[:3]
    return (r, g, b, alpha)
