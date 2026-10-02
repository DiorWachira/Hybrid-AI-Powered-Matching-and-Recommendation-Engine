import { useEffect, useState } from "react";
import { Network, Pencil, RefreshCw, Save, Search } from "lucide-react";
import { api, type OntologyData, type OntologyRelation, type OntologySkill } from "../lib/api";

export function OntologyEditor() {
  const [data, setData] = useState<OntologyData>({skills:[],relationships:[]});
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [skill, setSkill] = useState<OntologySkill>({name:"",category:"",source:""});
  const [relation, setRelation] = useState<OntologyRelation>({source_skill:"",target_skill:"",weight:0.5,source:""});
  const [remove, setRemove] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.ontology(localStorage.getItem("jobbridge_token") ?? "", query).then((value) => { if(active) setData(value); })
      .catch((reason: Error) => { if(active) setError(reason.message); })
      .finally(() => { if(active) setLoading(false); });
    return () => { active=false; };
  }, [query,refresh]);
  const save = async (event: React.FormEvent, kind: "skill" | "relation") => {
    event.preventDefault();
    if(kind === "relation" && remove && !window.confirm("Remove this related-skill link?")) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const token=localStorage.getItem("jobbridge_token") ?? "";
      if(kind === "skill") await api.saveSkill(token,skill); else await api.saveRelation(token,relation,remove);
      setNotice(kind === "skill" ? "Skill saved." : remove ? "Relationship removed." : "Relationship saved."); setRefresh(value=>value+1);
    } catch(reason) { setError(reason instanceof Error ? reason.message : "Ontology update failed."); }
    finally { setBusy(false); }
  };
  return <section className="data-section" aria-label="Skill ontology">
    <h2 className="section-heading"><Network size={18}/>Skill ontology</h2>
    {error && <p className="notice error" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
    <form className="admin-search" onSubmit={event=>{event.preventDefault();setQuery(search.trim());}}><label className="studio-field">Find skill<input type="search" maxLength={120} value={search} onChange={event=>setSearch(event.target.value)}/></label><button className="secondary-button"><Search size={16}/>Search ontology</button><button type="button" className="icon-button" aria-label="Refresh ontology" title="Refresh ontology" disabled={loading} onClick={()=>setRefresh(value=>value+1)}><RefreshCw size={16}/></button></form>
    <div className="form-grid">
      <form onSubmit={event=>void save(event,"skill")}><h3>Skill</h3><label className="studio-field">Skill name<input value={skill.name} maxLength={120} required onChange={event=>setSkill({...skill,name:event.target.value})}/></label><label className="studio-field">Category<input value={skill.category ?? ""} maxLength={120} required onChange={event=>setSkill({...skill,category:event.target.value})}/></label><label className="studio-field">Skill source<input value={skill.source ?? ""} maxLength={255} required onChange={event=>setSkill({...skill,source:event.target.value})}/></label><button className="secondary-button" disabled={busy}><Save size={16}/>Save skill</button></form>
      <form onSubmit={event=>void save(event,"relation")}><h3>Related skills</h3><label className="studio-field">Source skill<select required value={relation.source_skill} onChange={event=>setRelation({...relation,source_skill:event.target.value})}><option value="">Select skill</option>{data.skills.map(item=><option key={item.name}>{item.name}</option>)}</select></label><label className="studio-field">Target skill<select required value={relation.target_skill} onChange={event=>setRelation({...relation,target_skill:event.target.value})}><option value="">Select skill</option>{data.skills.map(item=><option key={item.name}>{item.name}</option>)}</select></label><label className="studio-field">Weight<input type="number" min={0} max={1} step={0.01} required value={relation.weight} onChange={event=>setRelation({...relation,weight:Number(event.target.value)})}/></label><label className="studio-field">Relationship source<input value={relation.source ?? ""} maxLength={255} required onChange={event=>setRelation({...relation,source:event.target.value})}/></label><label><input type="checkbox" checked={remove} onChange={event=>setRemove(event.target.checked)}/> Remove relationship</label><button className="secondary-button" disabled={busy}><Save size={16}/>{remove ? "Remove link" : "Save link"}</button></form>
    </div>
    <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Skill</th><th>Category</th><th>Source</th><th>Edit</th></tr></thead><tbody>{data.skills.map(item=><tr key={item.name}><td>{item.name}</td><td>{item.category ?? "Unspecified"}</td><td>{item.source ?? "Unverified"}</td><td><button className="icon-button" title={`Edit ${item.name}`} aria-label={`Edit ${item.name}`} onClick={()=>setSkill(item)}><Pencil size={15}/></button></td></tr>)}{!data.skills.length && <tr><td colSpan={4}>{loading ? "Loading skills..." : "No skills found"}</td></tr>}</tbody></table></div>
    <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Source skill</th><th>Target skill</th><th>Weight</th><th>Source</th><th>Edit</th></tr></thead><tbody>{data.relationships.map((item,index)=><tr key={`${item.source_skill}-${item.target_skill}-${index}`}><td>{item.source_skill}</td><td>{item.target_skill}</td><td>{item.weight}</td><td>{item.source ?? "Unverified"}</td><td><button className="icon-button" title="Edit relationship" aria-label={`Edit link ${item.source_skill} to ${item.target_skill}`} onClick={()=>{setRelation(item);setRemove(false);}}><Pencil size={15}/></button></td></tr>)}</tbody></table></div>
  </section>;
}