// 문서함 — 디자인 DocBox.dc.html. 서버 문서함(@cw/data/useDocBox, API_CONTRACT 23절)으로 그린다.
//  - 폴더 · 올리기 · 폴더 옮기기 · 내려받기 · 첫 페이지 미리보기(글 · 그림)는 서버 값. 디자인의 예시 문서(임시 안내 글 두 개)는 뺐다.
//  - 문서함은 모든 상담사가 같이 본다(서버가 사용자별로 나누지 않는다). 그래서 안내 줄에 '어르신 개인정보가 든 문서는 올리지 마세요' 를 띄운다.
//  - 빈 양식(S-01~S-08 · 점검표 · 참고 척도): 디자인에 들어 있는 기관 양식 틀이다. '빈 양식' 칸에 보이고 빈칸에 입력해 볼 수 있지만
//    서버 저장은 없다(작성한 서식이 공용 문서함에 올라가 다른 상담사에게 보이면 안 되므로). '저장' 은 준비 중 안내, '다운로드' 는 HTML 로 받는다.
//  - 지우기는 디자인 화면에 단추가 없어 두지 않았다(서버는 관리자만 지울 수 있다).
import { useDC } from '../dc';
import DesignLogic from '../design/DocBox.logic';
import { useDocBox } from '@cw/data/useDocBox';
import { useShell } from '../data/useShell';
import View from './DocBox.view';

const ALL = 'all';
const BLANK = 'blank';
const NONE = 'none';
const NOTICE = '문서함은 모든 상담사에게 보여요 · 어르신 개인정보가 든 문서는 올리지 마세요';

const fmtSize = (n) => (n < 1024 ? `${n}B` : n < 1048576 ? `${Math.round(n / 102.4) / 10}KB` : `${Math.round(n / 104857.6) / 10}MB`);
const extOf = (n) => {
  const m = /\.([^.]+)$/.exec(n || '');
  return m ? m[1].toUpperCase() : 'FILE';
};
const pad = (x) => String(x).padStart(2, '0');
const ymdOf = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    // 디자인 예시 문서 가운데 빈 양식 틀만 남기고 '빈 양식' 칸에 둔다. 디자인 폴더(기관 서식 · 참고 자료)는 서버 폴더로 바꾼다.
    const forms = this.state.docs.filter((d) => d.kind === 'form').map((d) => ({ ...d, folder: BLANK }));
    this.state = { ...this.state, cur: ALL, folders: [], docs: forms, msg: '' };
  }

  renderValsBase() {
    const s = this.state;
    const { box } = this.props;
    const data = box.data;
    const sFolders = data ? data.folders : [];
    const files = data ? data.files : [];
    const forms = s.docs;
    const fname = (id) =>
      id === BLANK ? '빈 양식' : !id || id === NONE ? '폴더 없음' : (sFolders.find((f) => f.id === id) || { name: '폴더 없음' }).name;

    const folders = [
      { id: ALL, name: '전체 문서', count: files.length + forms.length },
      { id: BLANK, name: '빈 양식', count: forms.length },
      ...sFolders,
    ].map((f) => ({
      name: f.name,
      count: f.count,
      cls: s.cur === f.id ? 'fold on' : 'fold',
      pressed: s.cur === f.id ? 'true' : 'false',
      pick: () => this.setState({ cur: f.id }),
    }));

    const opts = [{ id: NONE, name: '폴더 없음' }].concat(sFolders.map((f) => ({ id: f.id, name: f.name })));
    const inFolder = (file) => s.cur === ALL || file.folder_id === s.cur;
    const list = [
      ...(s.cur === ALL || s.cur === BLANK ? forms.map((d) => ({ d, form: true, ts: 0 })) : []),
      ...files.filter(inFolder).map((f) => ({ d: f, form: false, ts: Date.parse(f.created_at) || 0 })),
    ];
    const pk = s.pk || null;
    const sk = pk ? pk.k : 'date';
    const first = pk ? pk.first : true;
    list.sort((a, b) =>
      sk === 'date'
        ? first ? b.ts - a.ts : a.ts - b.ts
        : first ? a.d.name.localeCompare(b.d.name, 'ko', { numeric: true }) : b.d.name.localeCompare(a.d.name, 'ko', { numeric: true }),
    );

    const formDownload = (d) => () => {
      try {
        const blob = new Blob([this.fHtml(d)], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${d.name}.html`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
        this.setState({ msg: `‘${d.name}’ 내려받기를 시작했어요` });
      } catch (e) {
        this.setState({ msg: '이 환경에서는 내려받기를 할 수 없어요' });
      }
    };
    const fileDownload = (f) => async () => {
      if (await box.download(f.id, f.name)) this.setState({ msg: `‘${f.name}’ 내려받기를 시작했어요` });
    };

    const formDoc = (d) => {
      const FD = this.formDefs()[d.form];
      return {
        name: d.name, folder: BLANK, ext: 'FORM', url: '', isImg: false, isText: false, isForm: true, isOther: false,
        pv: this.fPages(d, true),
        open: () => this.setState({ fm: d.id, fmMode: 'edit', fmDirty: false, fmSaved: '' }),
        view: () => this.setState({ fm: d.id, fmMode: 'view', fmDirty: false, fmSaved: '' }),
        pvTitle: d.name, pvBody: '', pvLabel: `${d.name} 첫 페이지 미리보기`,
        meta: `빈 양식 · ${FD.pages}쪽`,
        opts: [{ id: BLANK, name: '빈 양식' }], mvLabel: `${d.name} 폴더 옮기기`,
        download: formDownload(d),
        move: () => {},
      };
    };
    const fileDoc = (f) => {
      const lines = (f.preview_text || '').split('\n');
      const url = box.imageUrls[f.id] || '';
      const isImg = f.preview_kind === 'image' && !!url;
      const isText = f.preview_kind === 'text';
      const by = f.uploaded_by_name ? ` · ${f.uploaded_by_name}` : '';
      return {
        name: f.name, folder: f.folder_id || NONE, ext: extOf(f.name), url, isImg, isText, isForm: false, isOther: !isImg && !isText,
        pv: [],
        open: () => {},
        view: () => this.setState({ fm: `file:${f.id}`, fmMode: 'view', fmDirty: false, fmSaved: '' }),
        pvTitle: lines[0] || f.name, pvBody: lines.slice(1, 22).join('\n'), pvLabel: `${f.name} 첫 페이지 미리보기`,
        meta: `${ymdOf(f.created_at)} · ${fmtSize(f.size_bytes)} · ${extOf(f.name)}${s.cur === ALL ? ' · ' + fname(f.folder_id) : ''}${by}`,
        opts, mvLabel: `${f.name} 폴더 옮기기`,
        download: fileDownload(f),
        move: async (e) => {
          const v = e.target.value;
          const target = v === NONE ? null : v;
          if (box.busy || target === f.folder_id) return;
          if (await box.move(f.id, target)) this.setState({ msg: `‘${f.name}’을(를) ${fname(target)}(으)로 옮겼어요` });
        },
      };
    };
    const docs = list.map((x) => (x.form ? formDoc(x.d) : fileDoc(x.d)));

    const onUpload = async (e) => {
      const picked = Array.from((e && e.target && e.target.files) || []);
      try {
        e.target.value = '';
      } catch (err) {
        /* 같은 파일을 다시 고를 수 있게 비운다 */
      }
      if (!picked.length || box.busy) return;
      const folder = s.cur === ALL || s.cur === BLANK ? null : s.cur;
      const count = await box.upload(picked, folder);
      if (count > 0) this.setState({ msg: `${count}개 문서를 ${fname(folder)}에 올렸어요`, cur: s.cur === BLANK ? ALL : s.cur });
    };

    const sorts = [['date', '날짜'], ['name', '이름']].map(([v, l]) => {
      const on = !!pk && pk.k === v;
      return {
        label: on ? l + (first ? '↑' : '↓') : l, cls: on ? 'on' : '', pressed: on ? 'true' : 'false',
        pick: () => this.setState({ pk: on ? { k: v, first: !first } : { k: v, first: true } }),
      };
    });
    const addFolder = async () => {
      const n = (s.newName || '').trim();
      if (!n || box.busy) return;
      const id = await box.createFolder(n);
      if (id) this.setState({ cur: id, adding: false, newName: '', msg: `‘${n}’ 폴더를 만들었어요` });
    };

    // 열어 보기 창: 빈 양식은 디자인 그대로(입력은 이 화면에만), 서버 문서는 서버가 뽑은 앞부분 글 · 그림만 보인다.
    const fmForm = s.fm && !String(s.fm).startsWith('file:') ? forms.find((x) => x.id === s.fm) : null;
    const fmFile = s.fm && String(s.fm).startsWith('file:') ? files.find((x) => `file:${x.id}` === s.fm) : null;
    const fmOpen = !!(fmForm || fmFile);
    const fmViewing = !!fmFile || (!!fmForm && s.fmMode === 'view');
    const fmImgUrl = fmFile ? box.imageUrls[fmFile.id] || '' : '';
    const fmV = {
      fmOpen,
      fmName: fmForm ? fmForm.name : fmFile ? fmFile.name : '',
      fmPages: fmForm ? this.fPages(fmForm, false, fmViewing) : [],
      fmEdit: !!fmForm && !fmViewing, fmView: fmViewing, fmCanEdit: !!fmForm, fmToEdit: () => this.setState({ fmMode: 'edit' }),
      fmIsText: !!fmFile && fmFile.preview_kind === 'text', fmText: fmFile ? fmFile.preview_text || '' : '',
      fmIsImg: !!fmFile && fmFile.preview_kind === 'image' && !!fmImgUrl, fmImg: fmImgUrl,
      fmIsOther: !!fmFile && !(fmFile.preview_kind === 'text') && !(fmFile.preview_kind === 'image' && fmImgUrl),
      fmState: fmViewing
        ? fmFile ? '내용 보기 · 앞부분만 · 전체는 다운로드로 확인' : '내용 보기 · 읽기 전용'
        : s.fmSaved ? s.fmSaved : s.fmDirty ? '작성 중 · 저장하지 않은 내용이 있어요' : '빈칸을 눌러 바로 작성할 수 있어요',
      // 작성한 서식 저장은 준비 중(공용 문서함에 개인정보가 올라가지 않게). 내려받기로 보관한다.
      fmSave: () => this.setState({ fmSaved: '저장은 준비 중이에요 · 다운로드로 내려받아 보관해 주세요' }),
      fmClose: () => this.setState({ fm: null, sv: null }),
      svOpen: false, svTitle: '', svName: '', svFolder: NONE, svErr: false, svOpts: [], svStop: () => {}, svSetName: () => {}, svSetFolder: () => {},
      svClose: () => this.setState({ sv: null }), svOk: () => this.setState({ sv: null }),
      fmDown: fmForm ? formDownload(fmForm) : fmFile ? fileDownload(fmFile) : () => {},
      fmClear: () => {
        const fv = { ...(this.state.fv || {}) };
        delete fv[s.fm];
        this.setState({ fv, fmDirty: true, fmSaved: '' });
      },
    };

    const msg = box.actionError || (box.busy ? '처리하는 중…' : s.msg) || (box.error ? box.error : box.loading && !data ? '문서함을 불러오는 중…' : NOTICE);
    return {
      ...fmV, folders, docs, hasDocs: docs.length > 0, noDocs: docs.length === 0, shownCount: docs.length,
      curName: s.cur === ALL ? '전체 문서' : fname(s.cur), sorts, onUpload,
      adding: s.adding, newName: s.newName, newLabel: s.adding ? '닫기' : '+ 새 폴더',
      toggleNew: () => this.setState({ adding: !s.adding, newName: '' }),
      setNewName: (e) => this.setState({ newName: e.target.value }), addFolder,
      hasMsg: !!msg, msg,
    };
  }

  renderVals() {
    return { ...super.renderVals(), ...this.props.shell, navLinkCnt: '', navFollowCnt: '' };
  }
}

export default function DocBox(props) {
  const shell = useShell();
  const box = useDocBox(shell.session);
  const v = useDC(Logic, { ...props, shell, box });
  return <View v={v} />;
}
