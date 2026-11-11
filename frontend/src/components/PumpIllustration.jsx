import { useEffect, useState } from 'react'

// Original line illustration of a two-line, cassette-based infusion pump.
// It is a generic drawing, not a reproduction of the real device or its
// branding. Drop a photo you have rights to at public/product/hero.jpg to
// show it instead.
function Drawing() {
  const keys = []
  for (let row = 0; row < 4; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      keys.push(
        <rect
          key={`${row}-${col}`}
          className="pump-key"
          x={214 + col * 26}
          y={206 + row * 20}
          width="20"
          height="14"
          rx="3"
        />,
      )
    }
  }

  return (
    <svg className="pump-drawing" viewBox="0 0 400 340" role="img" aria-labelledby="pump-title">
      <title id="pump-title">Illustration of a two-line infusion pump</title>

      {/* I.V. pole behind the infuser */}
      <rect className="pump-pole" x="352" y="0" width="8" height="340" rx="4" />
      <rect className="pump-clamp" x="326" y="146" width="40" height="34" rx="6" />

      {/* Tubing: Lines A and B in, one patient line out */}
      <path className="pump-tube" d="M98 74 C 98 40, 70 30, 62 0" />
      <path className="pump-tube" d="M118 74 C 118 36, 140 24, 146 0" />
      <path className="pump-tube" d="M108 290 C 108 316, 96 328, 80 340" />

      {/* Body */}
      <rect className="pump-body" x="58" y="56" width="276" height="246" rx="26" />

      {/* Cassette door with cassette */}
      <rect className="pump-door" x="76" y="74" width="66" height="210" rx="14" />
      <rect className="pump-cassette" x="90" y="96" width="38" height="124" rx="6" />
      <path className="pump-cassette-line" d="M100 112v92M118 112v92M100 150h18" />
      <circle className="pump-cassette-dot" cx="109" cy="176" r="5" />
      <rect className="pump-handle" x="98" y="240" width="22" height="30" rx="5" />

      {/* Display */}
      <rect className="pump-bezel" x="160" y="74" width="158" height="112" rx="12" />
      <rect className="pump-screen" x="170" y="84" width="138" height="82" rx="6" />
      <line className="pump-screen-rule" x1="239" y1="92" x2="239" y2="158" />
      <text className="pump-screen-label" x="180" y="100">A</text>
      <text className="pump-screen-label" x="249" y="100">B</text>
      <text className="pump-screen-value" x="180" y="130">125</text>
      <text className="pump-screen-value" x="249" y="130">40</text>
      <text className="pump-screen-unit" x="180" y="146">mL/hr</text>
      <text className="pump-screen-unit" x="249" y="146">mL/hr</text>
      <rect className="pump-screen-bar" x="180" y="152" width="44" height="4" rx="2" />
      <rect className="pump-screen-bar is-muted" x="249" y="152" width="28" height="4" rx="2" />
      {[0, 1, 2, 3].map((index) => (
        <rect
          key={index}
          className="pump-softkey"
          x={170 + index * 36}
          y="172"
          width="30"
          height="8"
          rx="3"
        />
      ))}

      {/* Keypad and start/stop */}
      {keys}
      <circle className="pump-start" cx="186" cy="218" r="9" />
      <circle className="pump-stop" cx="186" cy="246" r="9" />
      <circle className="pump-power" cx="186" cy="274" r="9" />
      <rect className="pump-key is-accent" x="292" y="206" width="20" height="74" rx="4" />
    </svg>
  )
}

const PHOTO_URL = '/product/hero.jpg'

export function PumpIllustration() {
  const [hasPhoto, setHasPhoto] = useState(false)

  // Show the drawing immediately; switch to a local photo only if one loads.
  useEffect(() => {
    const probe = new Image()
    probe.onload = () => setHasPhoto(true)
    probe.src = PHOTO_URL
    return () => {
      probe.onload = null
    }
  }, [])

  return hasPhoto ? (
    <img className="pump-photo" src={PHOTO_URL} alt="Plum 360 infuser" />
  ) : (
    <Drawing />
  )
}
