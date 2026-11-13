Shader "Inkline/PaperInk"
{
    Properties
    {
        _Color ("Paper color", Color) = (1,1,1,1)
        _Shade ("Ink shadow", Color) = (0.13,0.08,0.23,1)
        _Dots ("Halftone amount", Range(0,1)) = 0.12
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            struct appdata { float4 vertex : POSITION; float3 normal : NORMAL; };
            struct v2f { float4 pos : SV_POSITION; float3 normal : TEXCOORD0; float3 world : TEXCOORD1; };
            fixed4 _Color, _Shade;
            float _Dots;
            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.normal = UnityObjectToWorldNormal(v.normal);
                o.world = mul(unity_ObjectToWorld, v.vertex).xyz;
                return o;
            }
            fixed4 frag(v2f i) : SV_Target
            {
                float lit = dot(normalize(i.normal), normalize(float3(-0.4,0.8,-0.6)));
                fixed3 col = lerp(_Shade.rgb, _Color.rgb, step(0.03,lit)*0.78+0.22);
                float2 dots = frac(i.world.xy*7.5)-0.5;
                float mask = 1-step(0.115,length(dots));
                col = lerp(col, _Shade.rgb, mask*_Dots);
                return fixed4(col,1);
            }
            ENDCG
        }
    }
    FallBack "Unlit/Color"
}
