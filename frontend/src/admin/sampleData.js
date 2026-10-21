/**
 * SAMPLE query log for the admin dashboard. The backend doesn't record topics or inquiry
 * states yet, so the dashboard runs on this made-up data. Replace loadQueryLog() with an API
 * call returning the same shape once the backend logs it.
 *
 * One record per question a student asked:
 *   { id, question, topic, student: {name, email} | null, source, confidence,
 *     status: 'answered' | 'rerouted' | 'pending' | 'resolved',   // see STATES in report.js
 *     askedAt, repliedAt, escalatedAt, resolvedAt,   // ISO strings or null
 *     ticket: {ref, officeName, answer, answeredBy} | null,
 *     flag: {by, at} | null }   // set when flagged as offensive or off-topic
 */

export const TOPICS = [
  'Enrollment',
  'Tuition & fees',
  'Scholarships',
  'Grades & exams',
  'Attendance',
  'Uniform & dress code',
  'Conduct & discipline',
  'Student ID',
  'Records & graduation',
  'Organizations & events',
  'Guidance & wellbeing',
  'Library & facilities',
  'Other',
];

const OFFICES = {
  registrar: "Registrar's Office",
  accounting: 'Accounting / Cashier',
  scholarships: 'Scholarship Office',
  'student-affairs': 'Office of Student Affairs',
  guidance: 'Guidance Office',
};

// [question, topic, office it would go to, how often it comes up]
const QUESTIONS = [
  ['How many units is an overload?', 'Enrollment', 'registrar', 9],
  ['When is the last day of enrollment?', 'Enrollment', 'registrar', 8],
  ['Can I drop a subject after the midterms?', 'Enrollment', 'registrar', 6],
  ['When is the tuition payment due?', 'Tuition & fees', 'accounting', 8],
  ['Can I pay my tuition in installments?', 'Tuition & fees', 'accounting', 7],
  ['How do I apply for an academic scholarship?', 'Scholarships', 'scholarships', 6],
  ['What grade do I need to keep my scholarship?', 'Scholarships', 'scholarships', 4],
  ['What happens if I fail a major exam?', 'Grades & exams', 'registrar', 5],
  ['Who prepares the schedule for major examinations?', 'Grades & exams', 'registrar', 3],
  ['What happens if I am absent too many times?', 'Attendance', 'student-affairs', 7],
  ['Can male students wear earrings?', 'Uniform & dress code', 'student-affairs', 5],
  ['What is the policy on the school uniform?', 'Uniform & dress code', 'student-affairs', 6],
  ['What is the penalty for cheating in an exam?', 'Conduct & discipline', 'student-affairs', 3],
  ['How do I replace a lost student ID?', 'Student ID', 'student-affairs', 4],
  ['How do I request my transcript of records?', 'Records & graduation', 'registrar', 5],
  ['Where can I get counseling if I feel stressed?', 'Guidance & wellbeing', 'guidance', 3],
  ['How do I join a student organization?', 'Organizations & events', 'student-affairs', 2],
  ['Is the library open on Saturdays?', 'Library & facilities', 'student-affairs', 2],
];

// Messages that aren't school questions, or are rude. The assistant flags most of them; staff
// catch the rest.
const STRAYS = [
  'Can you write my essay on climate change for me?',
  'Who will win the NBA finals this year?',
  'What is a good recipe for chicken adobo?',
  'Tell me a joke',
  'This school is a joke and so are the teachers',
  'You are a useless stupid bot',
];

const STUDENTS = [
  'Andrea Reyes', 'Miguel Santos', 'Bea Mendoza', 'Paolo Garcia', 'Kyla Bautista', 'Joshua Cruz',
  'Nicole Ramos', 'Carlo Villanueva', 'Trisha Aquino', 'Mark Dela Cruz', 'Jasmine Castillo',
  'Rafael Torres', 'Angela Navarro', 'Kevin Flores', 'Sofia Lim', 'Daniel Pascual',
];

const OFFICE_REPLIES = [
  'Please visit our office with your student ID so we can check your records.',
  'Yes, as long as you file the request before the deadline posted on the bulletin board.',
  'This depends on your program. Your college dean can confirm it for you.',
];

// Enrollment and exam seasons rise and fall over the term, so the trends have a shape.
const SEASON = [1.0, 1.2, 1.0, 1.4, 0.8, 0.6]; // this month, last month, … and round again
const HISTORY = 14; // months of log, so last year shows up too

// A seeded generator: the same sample every load, so the numbers don't jump around.
function rng(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const plus = (date, minutes) => new Date(date.getTime() + minutes * 60_000);

function generate(now = new Date()) {
  const random = rng(2026);
  const pick = (list) => list[Math.floor(random() * list.length)];
  const records = [];
  let ticketNo = 1;

  for (let monthsAgo = HISTORY - 1; monthsAgo >= 0; monthsAgo -= 1) {
    const start = new Date(now.getFullYear(), now.getMonth() - monthsAgo, 1);
    const end = monthsAgo ? new Date(now.getFullYear(), now.getMonth() - monthsAgo + 1, 1) : now;
    for (const [question, topic, office, weight] of QUESTIONS) {
      const times = Math.round(weight * SEASON[monthsAgo % SEASON.length] * (0.4 + random() * 0.9));
      for (let i = 0; i < times; i += 1) {
        const askedAt = new Date(start.getTime() + random() * (end.getTime() - start.getTime()));
        const name = random() < 0.85 ? pick(STUDENTS) : null; // some ask without signing in
        const record = {
          question,
          topic,
          status: 'answered',
          student: name ? { name, email: `${name.toLowerCase().replace(/\s+/g, '.')}@ub.edu.ph` } : null,
          source: null,
          confidence: 0,
          askedAt: askedAt.toISOString(),
          repliedAt: plus(askedAt, 0.05).toISOString(),
          escalatedAt: null,
          resolvedAt: null,
          ticket: null,
          flag: null,
        };

        if (random() < 0.7) {
          record.source = `Student handbook, p. ${20 + Math.floor(random() * 140)}`;
          record.confidence = Math.round((0.55 + random() * 0.4) * 100) / 100;
        } else {
          record.status = 'rerouted';
          const minutesAgo = (now.getTime() - askedAt.getTime()) / 60_000;
          if (record.student && random() < 0.6 && minutesAgo > 5) {
            const escalatedAt = plus(askedAt, 2);
            record.status = 'pending';
            record.escalatedAt = escalatedAt.toISOString();
            record.ticket = {
              ref: `UBT-${String(ticketNo++).padStart(4, '0')}`,
              officeName: OFFICES[office],
              answer: null,
              answeredBy: null,
            };
            // Older questions have mostly been answered by now.
            const resolvedAt = plus(escalatedAt, 120 + random() * 4000);
            if (resolvedAt < now && random() < (monthsAgo ? 0.95 : 0.45)) {
              record.status = 'resolved';
              record.resolvedAt = resolvedAt.toISOString();
              record.ticket.answer = pick(OFFICE_REPLIES);
              record.ticket.answeredBy = `Staff, ${OFFICES[office]}`;
            }
          }
        }
        records.push(record);
      }
    }

    for (const question of STRAYS) {
      if (random() < 0.4) continue;
      const askedAt = new Date(start.getTime() + random() * (end.getTime() - start.getTime()));
      const name = random() < 0.6 ? pick(STUDENTS) : null;
      records.push({
        question,
        topic: 'Other',
        status: 'rerouted',
        student: name ? { name, email: `${name.toLowerCase().replace(/\s+/g, '.')}@ub.edu.ph` } : null,
        source: null,
        confidence: 0,
        askedAt: askedAt.toISOString(),
        repliedAt: plus(askedAt, 0.05).toISOString(),
        escalatedAt: null,
        resolvedAt: null,
        ticket: null,
        flag: random() < 0.7 ? { by: 'Assistant', at: plus(askedAt, 0.05).toISOString() } : null,
      });
    }
  }

  records.sort((a, b) => b.askedAt.localeCompare(a.askedAt));
  return records.map((r, i) => ({ ...r, id: records.length - i }));
}

/** The query log, newest first. Async so an API call can drop in here later. */
export async function loadQueryLog() {
  return generate();
}
