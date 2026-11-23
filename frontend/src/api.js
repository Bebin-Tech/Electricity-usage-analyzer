const base = import.meta.env.VITE_API_URL || '';
export async function api(path, {method='GET', body, blob=false}={}) {
  if(import.meta.env.VITE_BACKEND_PENDING==='true') throw new Error('The hosted backend is being connected. Sign-in and account features will be available once deployment setup is complete.');
  const token = sessionStorage.getItem('energy_token');
  const headers = token ? {Authorization:`Bearer ${token}`} : {};
  if (body && !(body instanceof FormData)) headers['Content-Type']='application/json';
  let response;
  try { response = await fetch(`${base}/api${path}`,{method,headers,body:body instanceof FormData ? body : body ? JSON.stringify(body) : undefined}); }
  catch { throw new Error('Cannot reach the API. Check that the backend is running.'); }
  if (!response.ok) {
    const data = await response.json().catch(()=>({}));
    if(response.status===401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('energy:logout'));
    throw new Error(Array.isArray(data.detail) ? data.detail.map(e=>`${e.loc.slice(1).join('.')}: ${e.msg}`).join('; ') : data.detail || (response.status>=500?'The server could not finish this request. Check the backend and database logs.':`Request failed (${response.status})`));
  }
  if(!blob && response.status!==204 && !response.headers.get('content-type')?.includes('application/json')) throw new Error('The backend is unavailable. Please try again after deployment setup is complete.');
  return blob ? response.blob() : response.status===204 ? null : response.json();
}
