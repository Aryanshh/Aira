"use client";

import * as React from "react";

export interface AiraLogoProps extends React.SVGProps<SVGSVGElement> {
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  variant?: "icon" | "mark";
  animateHeartbeat?: boolean;
}

const sizeMap = {
  xs: 24,
  sm: 32,
  md: 40,
  lg: 64,
  xl: 120,
};

export function AiraLogo({
  size = "md",
  variant = "icon",
  animateHeartbeat = false,
  className = "",
  ...props
}: AiraLogoProps) {
  const dimension = sizeMap[size];

  if (variant === "mark") {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 512 512"
        width={dimension}
        height={dimension}
        className={`${animateHeartbeat ? "animate-heartbeat" : ""} ${className}`}
        aria-label="AIRA Care Logo"
        role="img"
        {...props}
      >
        <defs>
          <linearGradient id="airaMarkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#D95338" />
            <stop offset="50%" stopColor="#B5472F" />
            <stop offset="100%" stopColor="#8E2D18" />
          </linearGradient>
        </defs>

        <g fill="none">
          {/* The Outer 'A' Frame: Sweeping Arched Shelter */}
          <path
            d="M 132 405 L 228 138 C 238 110 274 110 284 138 L 380 405"
            stroke="url(#airaMarkGrad)"
            strokeWidth="38"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Central Sculpted Heart (Crossbar of 'A') */}
          <path
            d="M 256 242
               C 244 218 214 208 194 226
               C 172 246 174 278 196 304
               L 256 364
               L 316 304
               C 338 278 340 246 318 226
               C 298 208 268 218 256 242 Z"
            fill="url(#airaMarkGrad)"
            stroke="url(#airaMarkGrad)"
            strokeWidth="6"
            strokeLinejoin="round"
          />

          {/* Dynamic Listening Pulse / EKG Wave inside the Heart */}
          <path
            d="M 188 285 L 220 285 L 232 255 L 248 318 L 264 268 L 276 285 L 324 285"
            stroke="#FFFFFF"
            strokeWidth="12"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Listening Crest / Voice Sensor Dot */}
          <circle cx="256" cy="180" r="14" fill="url(#airaMarkGrad)" />
        </g>
      </svg>
    );
  }

  // Variant: "icon" with Sunset Squircle
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
      width={dimension}
      height={dimension}
      className={`${animateHeartbeat ? "animate-heartbeat" : ""} ${className}`}
      aria-label="AIRA Care Icon"
      role="img"
      {...props}
    >
      <defs>
        <linearGradient id="airaIconBg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#D95338" />
          <stop offset="50%" stopColor="#B5472F" />
          <stop offset="100%" stopColor="#8E2D18" />
        </linearGradient>
        <linearGradient id="airaIconGloss" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Background Rounded Squircle */}
      <rect width="512" height="512" rx="124" fill="url(#airaIconBg)" />
      <rect width="512" height="512" rx="124" fill="url(#airaIconGloss)" />

      {/* Logo Mark: Pure White Elements */}
      <g fill="none">
        {/* The Outer 'A' Frame: Arched Shelter */}
        <path
          d="M 132 405 L 228 138 C 238 110 274 110 284 138 L 380 405"
          stroke="#FFFFFF"
          strokeWidth="38"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Central Sculpted Heart (Integrated Crossbar) */}
        <path
          d="M 256 242
             C 244 218 214 208 194 226
             C 172 246 174 278 196 304
             L 256 364
             L 316 304
             C 338 278 340 246 318 226
             C 298 208 268 218 256 242 Z"
          fill="#FFFFFF"
          stroke="#FFFFFF"
          strokeWidth="6"
          strokeLinejoin="round"
        />

        {/* EKG Lifeline / Listening Wave inside Heart */}
        <path
          d="M 188 285 L 220 285 L 232 255 L 248 318 L 264 268 L 276 285 L 324 285"
          stroke="#B5472F"
          strokeWidth="12"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Listening Crest / Voice Sensor Dot */}
        <circle cx="256" cy="180" r="14" fill="#FFFFFF" />
      </g>
    </svg>
  );
}
