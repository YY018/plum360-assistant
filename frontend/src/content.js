// Product page content. Every fact is taken from the Plum 360 System Operating
// Manual (IFU0000340); `ref` is the manual's own section-page number.

export const HERO = {
  eyebrow: 'Large-volume infusion system',
  title: 'Plum 360 infuser',
  lead:
    'A large-volume infuser for parenteral, enteral, and epidural therapies and ' +
    'the administration of whole blood and blood products. One cassette drives ' +
    'two lines at independent rates, delivered together or one after another, ' +
    'without raising or lowering I.V. bags.',
  ref: '1-1',
}

export const STATS = [
  { value: '2 lines', label: 'Independent rates from one cassette', ref: '1-1' },
  { value: '0.1–999', unit: 'mL/hr', label: 'Delivery rate range per line', ref: '11-6' },
  { value: '7 h', label: 'Typical battery time at 25 mL/hr', ref: '11-2' },
  { value: '4.5 kg', label: 'With battery, about 20 × 20 × 15 cm', ref: '11-1' },
]

export const FEATURES = [
  {
    icon: 'lines',
    title: 'Concurrent and piggyback delivery',
    text:
      'Lines A and B can run in Concurrent mode (together) or Piggyback mode ' +
      '(one after another), and a bolus dose can be programmed from either line.',
    ref: '1-1',
    ask: 'What is the difference between concurrent and piggyback delivery?',
  },
  {
    icon: 'valve',
    title: 'Positive valving cassette',
    text:
      'The proprietary Plum cassette in every administration set works with the ' +
      'pumping mechanism for accurate delivery and air management, and prevents ' +
      'free-flow conditions.',
    ref: '2-1',
    ask: 'How does the Plum cassette work?',
  },
  {
    icon: 'air',
    title: 'Air management at the bedside',
    text:
      'Proximal air in the line can be removed by backpriming, without ' +
      'disconnecting the patient line.',
    ref: '1-1',
    ask: 'How do I backprime to remove air in the line?',
  },
  {
    icon: 'network',
    title: 'Connectivity Engine',
    text:
      'Wired Ethernet and dual-band 802.11 a/b/g/n wireless connect to ICU Medical ' +
      'MedNet software for drug libraries, software updates, and auto-programming.',
    ref: '2-1',
    ask: 'What is the Connectivity Engine and what does it do?',
  },
  {
    icon: 'library',
    title: 'Drug libraries with limits',
    text:
      'Program with the default drug library or a custom library built for each ' +
      'clinical care area, with hard and soft dosing limits.',
    ref: '5-1',
    ask: 'What are hard limits and soft limits in the drug library?',
  },
  {
    icon: 'hardware',
    title: 'Designed for the ward',
    text:
      'IPX2 rating, a ratcheting pole clamp that prevents over-tightening, ' +
      'proximal tubing guides that help prevent kinks, and a tilted display.',
    ref: '1-1',
    ask: 'How do I mount the infuser on an I.V. pole?',
  },
]

export const STEPS = [
  {
    title: 'Mount the infuser',
    text: 'Attach it to an I.V. pole with the ratcheting pole clamp.',
    ref: '3-3',
    ask: 'How do I mount the infuser on an I.V. pole?',
  },
  {
    title: 'Prime the administration set',
    text: 'Fill the primary set and cassette with fluid before loading.',
    ref: '4-2',
    ask: 'How do I prime a primary administration set?',
  },
  {
    title: 'Load the cassette',
    text: 'Open the cassette door, insert the primed cassette, and close the door.',
    ref: '4-8',
    ask: 'How do I load a cassette?',
  },
  {
    title: 'Power on and program',
    text: 'Turn the infuser on and program Line A or Line B from the delivery screen.',
    ref: '3-10',
    ask: 'How do I turn on the infuser and program a line?',
  },
  {
    title: 'Start and monitor',
    text: 'Start delivery, then stop, restart, or clear a line as needed.',
    ref: '3-22',
    ask: 'How do I stop and restart a delivery?',
  },
]

export const ALARM_LEVELS = [
  { level: 'High', beeps: 10 },
  { level: 'Medium', beeps: 3 },
  { level: 'Low', beeps: 2 },
]
export const ALARM_REF = '9-1'
export const ALARM_NOTE =
  'The alarm system handles more than one alarm at a time and prioritizes them. ' +
  'Alarm loudness ranges from 45 to 70 dB, set by the control on the back of the infuser.'

export const CARE = [
  {
    title: 'Cleaning',
    text:
      'Wipe non-hazardous spills as soon as possible with an approved cleaning ' +
      'solution on a lint-free cloth. Never spray toward any opening, and do not ' +
      'use the infuser if the enclosure, keypad, or display is cracked.',
    ref: '10-2',
    ask: 'How do I clean the infuser?',
  },
  {
    title: 'Battery',
    text:
      'A sealed lead-acid battery charges whenever the infuser is on AC power, ' +
      'taking up to 8 hours. It runs about 7 hours at 25 mL/hr or 4 hours at ' +
      '999 mL/hr. If the low-battery alarm sounds, connect to AC power immediately.',
    ref: '11-2',
    ask: 'What should I do when the low battery alarm sounds?',
  },
  {
    title: 'Maintenance',
    text:
      'Annual preventive maintenance is performed by qualified service personnel. ' +
      'There is no clinician-required maintenance. Expected service life is 10 years.',
    ref: '10-4',
    ask: 'What maintenance does the infuser need?',
  },
]

export const SPECS = [
  ['Dimensions', 'About 20 × 20 × 15 cm (8 × 8 × 6 in), excluding pole clamp', '11-1'],
  ['Mass', 'About 4.5 kg (10 lb) with battery', '11-1'],
  ['Power', '100–120 VAC or 220–240 VAC, 50–60 Hz, 50 VA', '11-2'],
  ['Battery', 'Sealed lead-acid, rechargeable, 6 V', '11-2'],
  ['Rate, Lines A and B', '0.1–99.9 mL/hr in 0.1 steps; 100–999 mL/hr in 1 steps', '11-6'],
  ['Cumulative maximum', '500 mL/hr (A + B)', '11-6'],
  ['VTBI range', '0.1–9999 mL', '11-6'],
  ['Connectivity', 'Ethernet and 802.11 a/b/g/n, 2.4 / 5 GHz', '1-1'],
  ['Expected service life', '10 years', '11-1'],
]

export const INTENDED_USE =
  'Intended for use in clinical environments at the direction or under the ' +
  'supervision of licensed physicians or certified healthcare professionals who ' +
  'are trained in the use of the infuser.'
export const INTENDED_USE_REF = '1-2'
