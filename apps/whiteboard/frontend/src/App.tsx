/** App shell + a tiny hash router (no router dependency, deploy-safe on static). */

import { useEffect, useState } from 'react';
import { BoardList } from './components/BoardList';
import { SharedView } from './components/SharedView';
import { Editor } from './editor/Editor';

type Route = { name: 'home' } | { name: 'board'; id: string } | { name: 'shared'; token: string };

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, '');
  const parts = path.split('/').filter(Boolean);
  if (parts[0] === 'b' && parts[1]) return { name: 'board', id: parts[1] };
  if (parts[0] === 's' && parts[1]) return { name: 'shared', token: parts[1] };
  return { name: 'home' };
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  useEffect(() => {
    const onHash = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onHash);
    if (!window.location.hash) window.location.hash = '#/';
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Path-style share links (/s/<token>) also work: the SPA is served for any path.
  useEffect(() => {
    const m = window.location.pathname.match(/^\/s\/([^/]+)\/?$/);
    if (m && m[1] && route.name !== 'shared') {
      window.location.hash = `#/s/${m[1]}`;
    }
  }, [route.name]);

  if (route.name === 'board') {
    return (
      <Editor boardId={route.id} onBack={() => (window.location.hash = '#/')} />
    );
  }
  if (route.name === 'shared') {
    return <SharedView token={route.token} />;
  }
  return <BoardList onOpen={(id) => (window.location.hash = `#/b/${id}`)} />;
}
