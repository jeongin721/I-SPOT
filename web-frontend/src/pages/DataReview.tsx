import Header from '../components/Header';
import { mockData } from '../data/mockData';
import { FileSearch, ArrowRight } from 'lucide-react';
import './Dashboard.css';

export default function DataReview() {
  return (
    <div className="dashboard-container">
      <Header />
      <main className="dashboard-main">
        <section className="welcome-section">
          <div className="welcome-text">
            <h1>자료 검토</h1>
            <p className="subtitle">새로 접수된 자료나 승인이 필요한 내역을 확인합니다.</p>
          </div>
        </section>

        <div className="dashboard-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
          {mockData.reviews.map(r => (
            <div key={r.id} className="card action-card" style={{ margin: 0 }}>
              <div className="action-top" style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: 40, height: 40, borderRadius: '8px', background: '#fff0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#e53e3e' }}>
                    <FileSearch size={20} />
                  </div>
                  <h3 style={{ fontWeight: 700, fontSize: '1.2rem' }}>{r.childName} · {r.age}세</h3>
                </div>
                <span className={`tag ${r.tag === '우선 검토' ? 'red' : 'outline-blue'}`}>{r.tag}</span>
              </div>
              <p style={{ fontSize: '1.1rem', marginBottom: '24px', fontWeight: 500 }}>{r.title}</p>
              <div className="action-bottom" style={{ borderTop: '1px solid #f0f0f0', paddingTop: '16px' }}>
                <span className="meta">{r.date}</span>
                <button className="btn-text">상세 확인하기 <ArrowRight size={16} /></button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
