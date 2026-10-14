"""
GLSL Shader Generator for Viewport OpenGL Rendering.
Combines hardware texture sampling, A/B wipe comparison, exposure, gamma,
channel isolation, input color space linearization, and display view transforms.
"""
from dataclasses import dataclass


@dataclass
class ShaderUniforms:
    exposure_ev: float = 0.0
    gamma: float = 1.0
    channel_mode: int = 0      # 0: RGB, 1: R, 2: G, 3: B, 4: A, 5: Luma (Y)
    comparison_mode: int = 0   # 0: Off, 1: Wipe, 2: Split, 3: Difference
    wipe_position: float = 0.5 # 0.0 to 1.0
    wipe_angle_rad: float = 1.5707963  # 90 degrees (vertical wipe line)
    diff_boost: float = 1.0
    input_space: int = 0       # 0: sRGB, 1: ACEScg/Linear, 2: Raw, 3: Cineon Log, 4: ALEXA LogC, 5: ALEXA LogC Film, 6: Rec709, 7: Gamma 2.2
    view_transform: int = 0    # 0: sRGB, 1: ACES Filmic, 2: Raw, 3: Rec709, 4: Gamma 2.2


VERTEX_SHADER_SOURCE = """#version 330 core
layout (location = 0) in vec2 aPos;
layout (location = 1) in vec2 aTexCoord;

uniform mat4 uTransform;

out vec2 TexCoord;

void main()
{
    gl_Position = uTransform * vec4(aPos, 0.0, 1.0);
    TexCoord = aTexCoord;
}
"""

FRAGMENT_SHADER_SOURCE = """#version 330 core
in vec2 TexCoord;
out vec4 FragColor;

uniform sampler2D uTextureA;        // Primary media (A)
uniform sampler2D uTextureB;        // Reference media (B)
uniform bool uHasTextureB;

uniform float uExposure;            // Exposure in EV stops (linear gain = 2^uExposure)
uniform float uGain;                // Linear Gain multiplier (Foundry Nuke style, default 1.0)
uniform float uTotalGain;           // Precomputed fast gain = uGain * 2^uExposure
uniform float uSaturation;          // Linear Saturation multiplier (Foundry Nuke style, default 1.0)
uniform bool uApplySat;             // True if saturation != 1.0
uniform float uGamma;               // Display gamma (inverse power)
uniform float uGammaPower;          // Precomputed fast gamma power = 1.0 / max(0.001, abs(uGamma))
uniform bool uApplyGamma;           // True if gamma != 1.0
uniform int uChannelMode;           // 0: RGB, 1: R, 2: G, 3: B, 4: A, 5: Luma Y

// Colorspace & Viewer Uniforms
// 0: sRGB, 1: ACEScg/Linear, 2: Raw, 3: Cineon Log, 4: ALEXA LogC, 5: ALEXA LogC Film, 6: Rec709, 7: Gamma 2.2
uniform int uInputSpace;
// 0: sRGB Display, 1: ACES Filmic, 2: Raw, 3: Rec709, 4: Gamma 2.2
uniform int uViewTransform;

// Stereo 3D Uniforms: 0: Off, 1: Left, 2: Right, 3: Anaglyph, 4: Side-by-Side, 5: Difference
uniform int uStereoMode;

// A/B Comparison Uniforms
uniform int uComparisonMode;        // 0: Off, 1: Wipe, 2: Split, 3: Difference
uniform float uWipePos;             // 0.0 to 1.0
uniform float uWipeAngle;           // Angle in radians
uniform float uAspect;              // Media aspect ratio (width / height)
uniform float uDiffBoost;           // Multiplier for difference mode
uniform float uStackMix;            // Onion skin mix (0.0 to 1.0)
uniform vec4 uLayerAChannels;       // Active channels for Layer A (x=R, y=G, z=B, w=A)

// ASC CDL Uniforms
uniform bool uHasCdl;
uniform vec3 uCdlSlope;
uniform vec3 uCdlOffset;
uniform vec3 uCdlPower;
uniform float uCdlSat;

// 3D LUT Uniforms
uniform sampler3D uLut3D;
uniform bool uHasLut3D;

// Interactive Grading Uniforms
uniform vec3 uGradingGain;
uniform vec3 uGradingOffset;
uniform float uGradingGamma;
uniform float uGradingContrast;
uniform float uGradingSat;
uniform float uGradingHue;
uniform float uDisplayBrightness;
uniform bool uInvertColors;
uniform bool uShowOutOfRange;

// sRGB to linear conversion
vec3 srgb_to_linear(vec3 c) {
    vec3 higher = pow(max((c + vec3(0.055)) / 1.055, vec3(0.0)), vec3(2.4));
    vec3 lower = c / 12.92;
    return mix(lower, higher, greaterThan(c, vec3(0.04045)));
}

// Scene-linear to display sRGB transfer
vec3 linear_to_srgb(vec3 c) {
    vec3 higher = 1.055 * pow(max(c, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055;
    vec3 lower = 12.92 * c;
    return mix(lower, higher, greaterThan(c, vec3(0.0031308)));
}

// Cineon / DPX Log to Scene-Linear
vec3 cineon_to_linear(vec3 c) {
    vec3 x = (c * 1023.0 - 685.0) / 300.0;
    return max(vec3(0.0), (pow(vec3(10.0), x) - 0.010798) / 0.989202);
}

// ARRI ALEXA LogC v3 EI800 to Scene-Linear
vec3 alexa_logc_to_linear(vec3 x) {
    float cut = 0.1496582;
    float a = 0.247190;
    float b = 0.385537;
    float c = 0.078277;
    float d = 0.105910;
    float e = 5.253018;
    float f = 0.0400405;
    vec3 lin;
    for (int i = 0; i < 3; ++i) {
        if (x[i] > cut) {
            lin[i] = (pow(10.0, (x[i] - b) / a) - d) / c;
        } else {
            lin[i] = (x[i] - f) / e;
        }
    }
    return max(lin, vec3(0.0));
}

// ALEXA LogC Film to Linear (LogC + soft film contrast)
vec3 alexa_logc_film_to_linear(vec3 x) {
    vec3 lin = alexa_logc_to_linear(x);
    return pow(lin, vec3(1.15)) * 1.1;
}

// Rec.709 OETF to Scene-Linear
vec3 rec709_to_linear(vec3 c) {
    vec3 higher = pow(max((c + vec3(0.099)) / 1.099, vec3(0.0)), vec3(1.0 / 0.45));
    vec3 lower = c / 4.5;
    return mix(lower, higher, greaterThan(c, vec3(0.081)));
}

// Scene-Linear to Rec.709 Display
vec3 linear_to_rec709(vec3 c) {
    vec3 higher = 1.099 * pow(max(c, vec3(0.0)), vec3(0.45)) - 0.099;
    vec3 lower = 4.5 * c;
    return mix(lower, higher, greaterThan(c, vec3(0.018)));
}

// Gamma 2.2 to Scene-Linear
vec3 gamma22_to_linear(vec3 c) {
    return pow(max(c, vec3(0.0)), vec3(2.2));
}

// Scene-Linear to Gamma 2.2 Display
vec3 linear_to_gamma22(vec3 c) {
    return pow(max(c, vec3(0.0)), vec3(1.0 / 2.2));
}

// Narkowicz ACES filmic tone mapping fit for HDR
vec3 aces_filmic(vec3 x) {
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// RGB <-> HSV color utilities for Hue adjustment
vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main()
{
    vec4 colA = texture(uTextureA, TexCoord);
    vec4 colB = uHasTextureB ? texture(uTextureB, TexCoord) : colA;
    vec4 finalColor = colA;

    // 0. Stereo 3D Display Logic (Texture A = Left Eye, Texture B = Right Eye)
    if (uStereoMode == 1) {
        // Left Eye Only
        finalColor = colA;
    }
    else if (uStereoMode == 2 && uHasTextureB) {
        // Right Eye Only
        finalColor = colB;
    }
    else if (uStereoMode == 3 && uHasTextureB) {
        // Anaglyph Red-Cyan (High quality color matrix)
        // Red channel from Left Eye, Green and Blue channels from Right Eye
        vec3 anaglyphRgb = vec3(colA.r, colB.g, colB.b);
        finalColor = vec4(anaglyphRgb, max(colA.a, colB.a));
    }
    else if (uStereoMode == 4 && uHasTextureB) {
        // Side-by-Side Stereo Split
        if (TexCoord.x < 0.5) {
            vec2 sampleCoord = vec2(TexCoord.x * 2.0, TexCoord.y);
            finalColor = texture(uTextureA, sampleCoord);
        } else {
            vec2 sampleCoord = vec2((TexCoord.x - 0.5) * 2.0, TexCoord.y);
            finalColor = texture(uTextureB, sampleCoord);
        }
    }
    else if (uStereoMode == 5 && uHasTextureB) {
        // Stereo Difference
        vec3 sDiff = abs(colA.rgb - colB.rgb) * uDiffBoost;
        finalColor = vec4(sDiff, 1.0);
    }
    // 1. A/B Comparison Logic (when not in Stereo mode)
    else if (uComparisonMode == 1 && uHasTextureB) {
        // Isotropic linear wipe across angle with aspect ratio correction
        vec2 dir = vec2(cos(uWipeAngle), sin(uWipeAngle));
        float aspect = max(0.001, uAspect);
        float rMax = 0.5 * (aspect * abs(dir.x) + abs(dir.y));
        float p = (TexCoord.x - 0.5) * aspect * dir.x + (TexCoord.y - 0.5) * dir.y;
        float proj = (rMax > 0.0001) ? (p / (2.0 * rMax) + 0.5) : 0.5;
        finalColor = (proj < uWipePos) ? colA : colB;
    }
    else if (uComparisonMode == 2 && uHasTextureB) {
        // Side-by-side split
        if (TexCoord.x < 0.5) {
            vec2 sampleCoord = vec2(TexCoord.x * 2.0, TexCoord.y);
            finalColor = texture(uTextureA, sampleCoord);
        } else {
            vec2 sampleCoord = vec2((TexCoord.x - 0.5) * 2.0, TexCoord.y);
            finalColor = texture(uTextureB, sampleCoord);
        }
    }
    else if (uComparisonMode == 3 && uHasTextureB) {
        // Difference Mode
        vec3 diff = abs(colA.rgb - colB.rgb) * uDiffBoost;
        finalColor = vec4(diff, 1.0);
    }
    else if (uComparisonMode == 4 && uHasTextureB) {
        // Over (Alpha Composite with Onion Skin Mix & RGBA Channel Isolation)
        float effAlphaA = (uLayerAChannels.w > 0.5 ? colA.a : 1.0) * uStackMix;
        vec3 mixedRgb;
        mixedRgb.r = (uLayerAChannels.x > 0.5) ? mix(colB.r, colA.r, effAlphaA) : colB.r;
        mixedRgb.g = (uLayerAChannels.y > 0.5) ? mix(colB.g, colA.g, effAlphaA) : colB.g;
        mixedRgb.b = (uLayerAChannels.z > 0.5) ? mix(colB.b, colA.b, effAlphaA) : colB.b;
        float mixedAlpha = max(colA.a * uStackMix, colB.a);
        finalColor = vec4(mixedRgb, mixedAlpha);
    }
    else if (uComparisonMode == 5 && uHasTextureB) {
        // Add Mode
        vec3 addRgb = (colA.rgb + colB.rgb) * uDiffBoost;
        finalColor = vec4(addRgb, max(colA.a, colB.a));
    }
    else if (uComparisonMode == 6 && uHasTextureB) {
        // Difference (Inverted) Mode
        vec3 diffInv = clamp(vec3(1.0) - abs(colA.rgb - colB.rgb) * uDiffBoost, 0.0, 1.0);
        finalColor = vec4(diffInv, 1.0);
    }

    // 2. Input Colorspace Linearization
    vec3 linearRgb;
    if (uInputSpace == 0) {
        linearRgb = srgb_to_linear(finalColor.rgb);
    } else if (uInputSpace == 1) {
        linearRgb = finalColor.rgb; // ACEScg / Linear
    } else if (uInputSpace == 2) {
        linearRgb = finalColor.rgb; // Raw / Unmanaged
    } else if (uInputSpace == 3) {
        linearRgb = cineon_to_linear(finalColor.rgb);
    } else if (uInputSpace == 4) {
        linearRgb = alexa_logc_to_linear(finalColor.rgb);
    } else if (uInputSpace == 5) {
        linearRgb = alexa_logc_film_to_linear(finalColor.rgb);
    } else if (uInputSpace == 6) {
        linearRgb = rec709_to_linear(finalColor.rgb);
    } else if (uInputSpace == 7) {
        linearRgb = gamma22_to_linear(finalColor.rgb);
    } else {
        linearRgb = finalColor.rgb;
    }

    // 3. Fast Exposure & Gain in Scene-Linear Space
    linearRgb = linearRgb * uTotalGain;

    // Fast Saturation in Scene-Linear Space
    if (uApplySat) {
        float luma = dot(linearRgb, vec3(0.2126, 0.7152, 0.0722));
        linearRgb = mix(vec3(luma), linearRgb, uSaturation);
    }

    // 4. ASC CDL Evaluation (SOP: Slope, Offset, Power + Saturation)
    if (uHasCdl) {
        vec3 sop = pow(max(linearRgb * uCdlSlope + uCdlOffset, vec3(0.0)), max(uCdlPower, vec3(0.0001)));
        float luma = dot(sop, vec3(0.2126, 0.7152, 0.0722));
        linearRgb = max(vec3(0.0), mix(vec3(luma), sop, uCdlSat));
    }

    // 5. Interactive Color Grading Edits
    linearRgb = linearRgb * uGradingGain + uGradingOffset;
    if (uGradingGamma > 0.001 && abs(uGradingGamma - 1.0) > 0.001) {
        linearRgb = pow(max(linearRgb, vec3(0.0)), vec3(1.0 / uGradingGamma));
    }
    if (abs(uGradingContrast - 1.0) > 0.001) {
        linearRgb = max(vec3(0.0), (linearRgb - vec3(0.18)) * uGradingContrast + vec3(0.18));
    }
    if (abs(uGradingSat - 1.0) > 0.001) {
        float luma = dot(linearRgb, vec3(0.2126, 0.7152, 0.0722));
        linearRgb = max(vec3(0.0), mix(vec3(luma), linearRgb, uGradingSat));
    }
    if (abs(uGradingHue) > 0.01) {
        vec3 hsv = rgb2hsv(linearRgb);
        hsv.x = fract(hsv.x + uGradingHue / 360.0);
        linearRgb = hsv2rgb(hsv);
    }

    // 6. 3D LUT Evaluation
    if (uHasLut3D) {
        vec3 lutCoord = clamp(linearRgb, 0.0, 1.0);
        linearRgb = texture(uLut3D, lutCoord).rgb;
    }

    // 7. Display / View Transform
    vec3 displayRgb;
    if (uViewTransform == 1) {
        displayRgb = linear_to_srgb(aces_filmic(linearRgb));
    } else if (uViewTransform == 0) {
        displayRgb = linear_to_srgb(linearRgb);
    } else if (uViewTransform == 2) {
        displayRgb = linearRgb; // Raw / Pass-through
    } else if (uViewTransform == 3) {
        displayRgb = linear_to_rec709(linearRgb);
    } else if (uViewTransform == 4) {
        displayRgb = linear_to_gamma22(linearRgb);
    } else {
        displayRgb = linearRgb;
    }

    // 8. Fast Hardware-Accelerated Gamma & Display Brightness Trim
    if (uApplyGamma) {
        displayRgb = pow(max(displayRgb, vec3(0.0)), vec3(uGammaPower));
        if (uGamma < 0.0) {
            displayRgb = vec3(1.0) - displayRgb;
        }
    }
    if (abs(uDisplayBrightness) > 0.001) {
        displayRgb = displayRgb * pow(2.0, uDisplayBrightness);
    }

    // 9. Invert Colors
    if (uInvertColors) {
        displayRgb = vec3(1.0) - displayRgb;
    }

    // 10. Out-of-Range False-Color Zebra / Highlight
    if (uShowOutOfRange) {
        if (displayRgb.r > 1.0 || displayRgb.g > 1.0 || displayRgb.b > 1.0) {
            displayRgb = vec3(1.0, 0.0, 1.0); // Blown highlights in magenta
        } else if (displayRgb.r < 0.0 || displayRgb.g < 0.0 || displayRgb.b < 0.0) {
            displayRgb = vec3(0.0, 0.8, 1.0); // Crushed blacks in cyan
        }
    }

    // 11. Channel Solo Isolation
    if (uChannelMode == 1) {
        FragColor = vec4(vec3(displayRgb.r), 1.0);
    } else if (uChannelMode == 2) {
        FragColor = vec4(vec3(displayRgb.g), 1.0);
    } else if (uChannelMode == 3) {
        FragColor = vec4(vec3(displayRgb.b), 1.0);
    } else if (uChannelMode == 4) {
        FragColor = vec4(vec3(finalColor.a), 1.0);
    } else if (uChannelMode == 5) {
        float y = dot(displayRgb, vec3(0.2126, 0.7152, 0.0722));
        FragColor = vec4(vec3(y), 1.0);
    } else {
        FragColor = vec4(displayRgb, finalColor.a);
    }
}
"""


def build_fragment_shader() -> str:
    """Return the GLSL fragment shader source code."""
    return FRAGMENT_SHADER_SOURCE

