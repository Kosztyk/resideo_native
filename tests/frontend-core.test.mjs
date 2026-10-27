import test from 'node:test';
import assert from 'node:assert/strict';
const path=new URL('../custom_components/resideo_native/www/schedule-editor.js',import.meta.url);
const {DAYS,normalizedDays,changedDays,validateDraft,makeSaveRequest,makeModeRequest,makeEnabledRequest,heatingWeekError}=await import(path.href);
const week=()=>Object.fromEntries(DAYS.map(d=>[d,[{time:'07:15:00',temperature:19},{time:'22:00:00',temperature:16}]]));
const base=()=>({revision:'original-revision',days:week(),temperature_limits:[5,35],write_supported:true,max_periods_per_day:6});

test('load normalization never edits source or invents a routine',()=>{
 const original=week(),copy=structuredClone(original),draft=normalizedDays(original);
 assert.equal(draft.Monday[0].time,'07:15');assert.deepEqual(original,copy);
 assert.ok(Object.values(normalizedDays({})).every(p=>p.length===0));
 assert.deepEqual(changedDays(original,draft),{});
});
test('save scopes changed days to the selected entity and current revision',()=>{
 const b=base(),draft=normalizedDays(b.days);draft.Monday[0].temperature=19.5;
 const request=makeSaveRequest('climate.upstairs',b,draft);
 assert.deepEqual(request.target,{entity_id:'climate.upstairs'});
 assert.equal(request.service,'set_heating_schedule');
 assert.deepEqual(Object.keys(request.service_data.days),['Monday']);
 assert.equal(request.service_data.expected_revision,'original-revision');
 assert.equal(request.return_response,true);assert.equal(request.service_data.confirm_conversion,undefined);
 assert.equal(b.days.Monday[0].temperature,19);
});
test('DHW serializes transitions and preserves off times',()=>{
 const b={revision:'dhw-revision',write_supported:true,days:Object.fromEntries(DAYS.map(d=>[d,[{time:'07:00',state:'On'},{time:'08:00',state:'Off'}]]))};
 const draft=structuredClone(b.days);draft.Monday[0].time='07:10';
 const r=makeSaveRequest('water_heater.hot_water',b,draft);
 assert.equal(r.service,'set_hot_water_schedule');assert.equal(r.service_data.days.Monday[1].time,'08:00');
});
test('conversion needs consent and all seven complete days',()=>{
 const b={...base(),days:{},requires_conversion:true,requires_full_week:true};
 assert.throws(()=>makeSaveRequest('climate.upstairs',b,week()),/Confirm/);
 assert.throws(()=>makeSaveRequest('climate.upstairs',b,{Monday:week().Monday},true),/weekday.*weekend/);
 const request=makeSaveRequest('climate.upstairs',b,week(),true);
 assert.equal(request.service_data.confirm_conversion,true);assert.equal(Object.keys(request.service_data.days).length,7);
});
test('first-time creation sends a complete week without pretending it is geofencing',()=>{
 const b={...base(),days:{},requires_full_week:true};
 const r=makeSaveRequest('climate.upstairs',b,week());assert.equal(Object.keys(r.service_data.days).length,7);
 assert.equal(r.service_data.confirm_conversion,undefined);
});
for(const [label,periods] of [
 ['duplicate times',[{time:'08:00',temperature:20},{time:'08:00',temperature:19}]],
 ['backwards times',[{time:'09:00',temperature:20},{time:'08:00',temperature:19}]],
 ['invalid time',[{time:'25:00',temperature:20}]],
 ['empty temperature',[{time:'08:00',temperature:null}]],
 ['out-of-range temperature',[{time:'08:00',temperature:80}]],
 ['NaN',[{time:'08:00',temperature:NaN}]],
 ['boolean temperature',[{time:'08:00',temperature:true}]],
 ['extra fields',[{time:'08:00',temperature:20,deviceIDs:['another']}]],
 ['periods must be a list',null],
 ['too many periods',Array.from({length:7},(_,i)=>({time:`0${i}:00`,temperature:20}))],
]) test('rejects '+label,()=>assert.ok(validateDraft({Monday:periods},false,[5,35])));
test('supports different day counts and thermostat Fahrenheit display',()=>{
 const b=base(),draft=normalizedDays(b.days);
 draft.Monday=[{time:'06:30',temperature:19},{time:'08:00',temperature:16},{time:'22:00',temperature:17}];
 assert.equal(makeSaveRequest('climate.downstairs',b,draft).service_data.days.Monday.length,3);
 assert.equal(validateDraft({Monday:[{time:'08:00',temperature:68}]},false,[41,95]),'');
});
test('unknown responses, missing revision and empty entity can never save',()=>{
 assert.throws(()=>makeSaveRequest('',base(),week()),/valid Resideo entity/);
 assert.throws(()=>makeSaveRequest('climate.upstairs',{write_supported:false},week()),/supported/);
 assert.throws(()=>makeSaveRequest('climate.upstairs',{},week()),/supported/);
 assert.throws(()=>makeSaveRequest('climate.upstairs',base(),week()),/no changes/);
});
test('invalid DHW states are rejected',()=>assert.ok(validateDraft({Monday:[{time:'08:00',state:true}]},true)));

test('an untouched empty cloud day does not block saving a different day',()=>{
 const b=base();b.days.Tuesday=[];
 const draft=normalizedDays(b.days);draft.Monday[0].temperature=19.5;
 const r=makeSaveRequest('climate.upstairs',b,draft);
 assert.deepEqual(Object.keys(r.service_data.days),['Monday']);
 assert.deepEqual(draft.Tuesday,[]);
});

test('removing the last heating period explicitly sends an empty changed day',()=>{
 const b=base(),draft=normalizedDays(b.days);draft.Monday=[];
 const r=makeSaveRequest('climate.upstairs',b,draft);
 assert.deepEqual(r.service_data.days,{Monday:[]});
 assert.equal(r.service_data.expected_revision,b.revision);
 assert.equal(b.days.Monday.length,2);
});
test('removing one of several heating periods retains the other entries',()=>{
 const b=base(),draft=normalizedDays(b.days);draft.Monday.splice(0,1);
 assert.deepEqual(makeSaveRequest('climate.upstairs',b,draft).service_data.days,{Monday:[{time:'22:00',temperature:16}]});
});
test('an existing DHW day may be cleared without inventing an Off transition',()=>{
 const b={...base(),days:{Monday:[{time:'07:00',state:'On'},{time:'08:00',state:'Off'}]}},draft=normalizedDays(b.days);draft.Monday=[];
 assert.deepEqual(makeSaveRequest('water_heater.hot_water',b,draft).service_data.days,{Monday:[]});
});
test('new heating routines and conversions allow empty days but retain both day groups',()=>{
 for(const conversion of [false,true]) {
   const b={...base(),days:{},requires_full_week:true,requires_conversion:conversion},draft=week();draft.Monday=[];
   assert.deepEqual(makeSaveRequest('climate.upstairs',b,draft,true).service_data.days.Monday,[]);
   draft.Saturday=[];draft.Sunday=[];
   assert.throws(()=>makeSaveRequest('climate.upstairs',b,draft,true),/weekday.*weekend/);
 }
});
test('full-week backups may contain empty days when editing an existing routine',()=>{
 const draft=week();draft.Monday=[];
 assert.equal(validateDraft(draft,false,[5,35],6,true,true),'');
 delete draft.Sunday;
 assert.ok(validateDraft(draft,false,[5,35],6,true,true));
});

test('an existing empty Timed week can be repaired with a weekday and weekend day',()=>{
 for(const fullWeekFlag of [true,false]) {
  const b={...base(),schedule_type:'Timed',days:normalizedDays({}),requires_full_week:fullWeekFlag};
  const draft=normalizedDays(b.days);draft.Monday=[{time:'08:00',temperature:20}];
  assert.throws(()=>makeSaveRequest('climate.upstairs',b,draft),/weekday.*weekend/);
  draft.Saturday=[{time:'09:00',temperature:19}];
  const r=makeSaveRequest('climate.upstairs',b,draft);
  assert.deepEqual(r.service_data.days,{Monday:[{time:'08:00',temperature:20}],Saturday:[{time:'09:00',temperature:19}]});
 }
});

test('deleting the final weekday or weekend day is blocked',()=>{
 const b=base();b.days=normalizedDays({Monday:week().Monday,Sunday:week().Sunday});
 for(const d of ['Monday','Sunday']){const draft=structuredClone(b.days);draft[d]=[];assert.throws(()=>makeSaveRequest('climate.upstairs',b,draft),/weekday.*weekend/);}
 assert.equal(heatingWeekError(b.days),'');
});
const controls=()=>({...base(),schedule_type:'Timed',schedule_controls_supported:true,schedule_following:true});
test('native schedule on/off addresses one climate entity without writing periods',()=>{
 for(const enabled of [false,true]){
  const r=makeEnabledRequest('climate.upstairs',controls(),enabled);
  assert.equal(r.service,'set_heating_schedule_enabled');assert.deepEqual(r.service_data,{enabled,expected_revision:'original-revision'});
 }
});
test('mode changes require explicit confirmation and valid user geofence values',()=>{
 const b=controls();assert.throws(()=>makeModeRequest('climate.upstairs',b,'Geofence',null,{home_temperature:20,away_temperature:16},false),/Confirm/);
 const r=makeModeRequest('climate.upstairs',b,'Geofence',null,{home_temperature:20,away_temperature:16},true);
 assert.equal(r.service,'set_heating_schedule_mode');assert.deepEqual(r.service_data.geofence,{home_temperature:20,away_temperature:16});assert.equal(r.service_data.days,undefined);
 for(const v of [null,true,100,NaN])assert.throws(()=>makeModeRequest('climate.upstairs',b,'Geofence',null,{home_temperature:v,away_temperature:16},true),/temperature/);
});
test('switching to Timed accepts two populated days and sends all seven lists',()=>{
 const b={...controls(),schedule_type:'Geofence'},draft=normalizedDays({Monday:week().Monday,Saturday:week().Saturday});
 const r=makeModeRequest('climate.upstairs',b,'Timed',draft,null,true);
 assert.equal(Object.keys(r.service_data.days).length,7);assert.equal(r.service_data.days.Tuesday.length,0);assert.equal(r.service_data.confirm_change,true);
});
test('unrecognized schedule controls, DHW and guessed None mode cannot write',()=>{
 assert.throws(()=>makeEnabledRequest('water_heater.hot_water',controls(),false),/supported heating/);
 assert.throws(()=>makeEnabledRequest('climate.upstairs',{...controls(),schedule_controls_supported:false},true),/supported heating/);
 assert.throws(()=>makeModeRequest('climate.upstairs',controls(),'None',null,null,true),/Timed or Geofence/);
});


const {scheduleEditorUrl,scheduleModeSwitchRequest}=await import(new URL('../custom_components/resideo_native/www/schedule-entity.js',import.meta.url));
test('only the schedule-editor entity opens the internal editor page',()=>{
 const hass={states:{'sensor.upstairs_schedule_editor':{attributes:{resideo_schedule_editor:true,editor_url:'/resideo-schedules?config_entry=account-a&entity=climate.upstairs'}}}};
 assert.equal(scheduleEditorUrl(hass,'sensor.upstairs_schedule_editor'),'/resideo-schedules?config_entry=account-a&entity=climate.upstairs');
 assert.equal(scheduleEditorUrl(hass,'climate.upstairs'),null);
 assert.equal(scheduleEditorUrl(hass,'sensor.other'),null);
 hass.states['sensor.upstairs_schedule_editor'].attributes.editor_url='https://example.com/resideo-schedules?config_entry=other';
 assert.equal(scheduleEditorUrl(hass,'sensor.upstairs_schedule_editor'),null);
});
test('DHW refuses 07:05 and accepts the native 07:10 increment',()=>{
 const b={revision:'r',write_supported:true,days:normalizedDays({Sunday:[{time:'07:00',state:'On'},{time:'08:00',state:'Off'}]})};
 const draft=structuredClone(b.days);draft.Sunday[0].time='07:05';
 assert.throws(()=>makeSaveRequest('water_heater.hot_water',b,draft),/10-minute/);
 draft.Sunday[0].time='07:10';assert.equal(makeSaveRequest('water_heater.hot_water',b,draft).service_data.days.Sunday[0].time,'07:10');
});
test('reported heating increments are checked before saving',()=>{
 const b={...base(),time_step_minutes:15},draft=normalizedDays(b.days);draft.Monday[0].time='07:05';
 assert.throws(()=>makeSaveRequest('climate.upstairs',b,draft),/15-minute/);
});


test('native On/Off does not validate or replace a sparse or inactive routine',()=>{
 for(const schedule_type of ['Timed','None']) for(const enabled of [false,true]) {
  const b={...controls(),schedule_type,days:normalizedDays({Friday:[{time:'06:30',temperature:19}]})};
  const request=makeEnabledRequest('climate.upstairs',b,enabled);
  assert.deepEqual(request.service_data,{enabled,expected_revision:'original-revision'});
  assert.equal(request.service_data.days,undefined);
 }
});

test('Geofencing switch chooses the two popup flows without changing observed state',()=>{
 const url='/resideo-schedules?config_entry=a&entity=climate.upstairs';
 const state={state:'off',attributes:{resideo_schedule_mode:true,editor_url:url}};
 const control={localName:'ha-switch',checked:false,disabled:false};
 const generic={localName:'hui-generic-entity-row',config:{entity:'switch.geofencing'},hass:{states:{'switch.geofencing':state}}};
 const event={type:'click',button:0,composedPath:()=>[control,generic]};
 assert.equal(scheduleModeSwitchRequest(event).mode,'Geofence');assert.equal(control.checked,false);
 state.state='on';assert.equal(scheduleModeSwitchRequest(event).mode,'Timed');
 state.attributes.resideo_schedule_mode=false;assert.equal(scheduleModeSwitchRequest(event),null);
 state.attributes.resideo_schedule_mode=true;control.disabled=true;assert.equal(scheduleModeSwitchRequest(event),null);
});

test('Geofence requests include explicit overnight sleep creation or removal',()=>{
 const b=controls(),sleep={start_time:'22:00',end_time:'06:00',temperature:16.5};
 assert.deepEqual(makeModeRequest('climate.upstairs',b,'Geofence',{}, {home_temperature:20,away_temperature:16,sleep},true).service_data.geofence.sleep,sleep);
 assert.equal(makeModeRequest('climate.upstairs',b,'Geofence',{}, {home_temperature:20,away_temperature:16,sleep:null},true).service_data.geofence.sleep,null);
 assert.throws(()=>makeModeRequest('climate.upstairs',b,'Geofence',{}, {home_temperature:20,away_temperature:16,sleep:{...sleep,end_time:'22:00'}},true),/different/);
});
