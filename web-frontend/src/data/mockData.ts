export const mockData = {
  user: {
    name: '이서연',
    role: '상담사',
    avatar: '이'
  },
  cases: [
    { id: 1, name: '박○준', age: 9, status: '정기 상담', session: 6, lastCounseling: '2026-09-25' },
    { id: 2, name: '최○나', age: 10, status: '초기 면담', session: 1, lastCounseling: null },
    { id: 3, name: '이○후', age: 12, status: '정기 상담', session: 3, lastCounseling: '2026-09-14' },
    { id: 4, name: '김○은', age: 8, status: '종결 대기', session: 12, lastCounseling: '2026-09-24' },
    { id: 5, name: '정○우', age: 11, status: '정기 상담', session: 4, lastCounseling: '2026-09-20' },
  ],
  schedules: [
    { id: 101, date: '2026-09-28', time: '13:00', endTime: '13:50', childName: '박○준', type: '정기 상담', desc: '6회기 · 지난 상담 기록과 오늘의 목표 확인', status: 'upcoming' },
    { id: 102, date: '2026-09-28', time: '14:30', endTime: '15:20', childName: '최○나', type: '초기 면담', desc: '초기 면담 · 1회기', status: 'upcoming' },
    { id: 103, date: '2026-09-28', time: '16:00', endTime: '16:50', childName: '이○후', type: '정기 상담', desc: '정기 상담 · 3회기', status: 'upcoming' },
    { id: 104, date: '2026-09-29', time: '10:00', endTime: '10:50', childName: '정○우', type: '정기 상담', desc: '정기 상담 · 5회기', status: 'scheduled' },
  ],
  reviews: [
    { id: 201, childName: '김○○', age: 8, title: '새로 접수된 상담 자료 확인', tag: '우선 검토', date: '오늘 09:20 접수' },
    { id: 202, childName: '박○○', age: 11, title: '상담 기록 검토 및 승인', tag: '오늘까지', date: '9월 25일 상담' },
  ],
  records: [
    { id: 301, childName: '박○준', title: '박○준 상담일지', status: '작성 대기', date: '9월 25일' },
    { id: 302, childName: '김○은', title: '김○은 상담일지', status: '임시 저장', date: '9월 24일' },
    { id: 303, childName: '정○우', title: '정○우 초기 상담일지', status: '작성 완료', date: '9월 20일' },
  ]
};
