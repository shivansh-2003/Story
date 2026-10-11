import { Input } from "@/components/ui/input";
import type { Character } from "@/lib/types";
import type { PlanFields, SceneFields } from "./planningApi";

export function PlanInputs({value, onChange, disabled}: {value:PlanFields; onChange:(next:PlanFields)=>void; disabled:boolean}) {
  return <div className="grid gap-3 sm:grid-cols-2">
    {([['objective','Objective'],['conflict','Conflict'],['ending_beat','Ending beat'],['notes','Notes']] as const).map(([key,label]) =>
      <label key={key} className="space-y-1 text-sm">{label}<textarea className="block min-h-20 w-full rounded-md border bg-background p-2" maxLength={2000} disabled={disabled} value={value[key]} onChange={e=>onChange({...value,[key]:e.target.value})} /></label>)}
  </div>;
}

export function SceneInputs({value, onChange, disabled, characters}: {value:SceneFields; onChange:(next:SceneFields)=>void; disabled:boolean; characters:Character[]}) {
  const available = new Set(characters.map(c=>c.id));
  const unavailable = value.character_ids.filter(id=>!available.has(id));
  return <div className="space-y-3">
    <label className="block space-y-1 text-sm">Scene title<Input value={value.title} maxLength={200} disabled={disabled} onChange={e=>onChange({...value,title:e.target.value})} /></label>
    <div className="grid gap-3 sm:grid-cols-2">
      {([['goal','Goal'],['conflict','Conflict'],['outcome','Intended outcome'],['setting','Setting'],['notes','Notes']] as const).map(([key,label])=>
        <label key={key} className="space-y-1 text-sm">{label}<textarea className="block min-h-16 w-full rounded-md border bg-background p-2" maxLength={1000} disabled={disabled} value={value[key]} onChange={e=>onChange({...value,[key]:e.target.value})} /></label>)}
    </div>
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="text-sm font-medium">Scene cast</legend>
      {characters.length === 0 && <p className="text-sm text-muted-foreground">Import characters through the story's Cast tab to assign a scene cast.</p>}
      {unavailable.length > 0 && <div className="text-sm text-muted-foreground">Some scene characters are no longer in the story cast. <button type="button" className="underline" disabled={disabled} onClick={()=>onChange({...value,character_ids:value.character_ids.filter(id=>available.has(id)),pov_character_id:value.pov_character_id && available.has(value.pov_character_id) ? value.pov_character_id : null})}>Remove unavailable characters</button></div>}
      <div className="flex flex-wrap gap-3">{characters.map(c=><label key={c.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={value.character_ids.includes(c.id)} onChange={e=>onChange({...value, character_ids:e.target.checked ? [...value.character_ids,c.id] : value.character_ids.filter(id=>id!==c.id), pov_character_id:!e.target.checked && value.pov_character_id===c.id ? null : value.pov_character_id})} />{c.name}</label>)}</div>
    </fieldset>
    <label className="block space-y-1 text-sm">POV character<select className="block w-full rounded-md border bg-background p-2" disabled={disabled} value={value.pov_character_id ?? ""} onChange={e=>onChange({...value,pov_character_id:e.target.value || null})}>
      <option value="">No specific POV character</option>{characters.filter(c=>value.character_ids.includes(c.id)).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
    </select></label>
  </div>;
}
