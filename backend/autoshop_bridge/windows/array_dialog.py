"""Observed Define Array modal only; no cell creation, grid read or persistence."""
import ctypes
from pathlib import Path
import time

from autoshop_bridge.errors import BridgeError


def _bind(function, arguments, result):
    if hasattr(function, 'argtypes'):
        function.argtypes, function.restype = arguments, result


def _process(adapter):
    a, w = adapter, adapter.types
    _bind(a.kernel.OpenProcess, [w.DWORD,w.BOOL,w.DWORD], w.HANDLE)
    _bind(a.kernel.CloseHandle, [w.HANDLE], w.BOOL)
    _bind(a.kernel.WaitForSingleObject, [w.HANDLE,w.DWORD], w.DWORD)
    _bind(a.kernel.GetProcessTimes, [w.HANDLE]+[ctypes.POINTER(w.FILETIME)]*4, w.BOOL)
    _bind(a.kernel.GetExitCodeProcess, [w.HANDLE,ctypes.POINTER(w.DWORD)], w.BOOL)
    _bind(a.kernel.QueryFullProcessImageNameW, [w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)], w.BOOL)
    handle = a.kernel.OpenProcess(0x101000, False, a.pid)
    if not handle:
        raise BridgeError('Cannot freeze ARRAY dialog process identity.')
    try:
        times=[w.FILETIME() for _ in range(4)];code=w.DWORD()
        image=ctypes.create_unicode_buffer(32768);size=w.DWORD(len(image))
        if (a.kernel.WaitForSingleObject(handle,0)!=0x102
                or not a.kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value!=259
                or not a.kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in times))
                or not a.kernel.QueryFullProcessImageNameW(handle,0,image,ctypes.byref(size))
                or Path(image.value).name.lower()!='autoshop.exe'
                or a.kernel.WaitForSingleObject(handle,0)!=0x102):
            raise BridgeError('ARRAY dialog process exited or identity could not be verified.')
        return dict(pid=a.pid,creation_time=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime,
                    executable=image.value)
    finally:
        a.kernel.CloseHandle(handle)


def _state(value):
    if (not isinstance(value,dict) or set(value)!={'element_type','dimensions','two_dimensional'}
            or not isinstance(value['element_type'],str) or not value['element_type']
            or not isinstance(value['dimensions'],(list,tuple)) or len(value['dimensions'])!=2
            or any(type(item) is not int or item<=0 for item in value['dimensions'])
            or type(value['two_dimensional']) is not bool):
        raise BridgeError('ARRAY expected_state requires exact element_type, two positive dimensions and two_dimensional boolean.')
    return dict(element_type=value['element_type'],dimensions=list(value['dimensions']),
                two_dimensional=value['two_dimensional'])


def _parent_controls(a,dialog):
    expected={('Edit',2819,None),('ComboBox',1408,None),('Button',1,'确定'),('Button',2,'取消'),
              ('Static',-1,'类型'),('Static',-1,'一维'),('Button',3143,'二维'),('Edit',2820,None)}
    controls={};children=a.children(dialog)
    if len(children)!=8:raise BridgeError('ARRAY dialog must have the observed eight direct controls.')
    for child in children:
        cls,cid=a.class_name(child),a.user.GetDlgCtrlID(child)
        key=(cls,cid,a.text(child) if cls in ('Button','Static') else None)
        if (key not in expected or key in controls or a.window_pid(child)!=a.pid
                or a.user.GetParent(child)!=dialog or not a.user.IsWindowVisible(child)):
            raise BridgeError('ARRAY dialog control identity/text/parent differs.')
        controls[key]=child
    two=a.window_message(controls[('Button',3143,'二维')],0x00F0)
    if two not in (0,1):raise BridgeError('ARRAY dimension checkbox has an unknown state.')
    for key,child in controls.items():
        if bool(a.user.IsWindowEnabled(child))!=(bool(two) if key==('Edit',2820,None) else True):
            raise BridgeError('ARRAY dialog control enabled state differs.')
    for cid,label in ((1,'确定'),(2,'取消')):
        if a.window_message(controls[('Button',cid,label)],0x00F0)!=0:
            raise BridgeError('ARRAY confirmation button check state differs.')
    combo=controls[('ComboBox',1408,None)];count=a.window_message(combo,0x0146)
    if not 1<=count<=4096:raise BridgeError('Unsupported ARRAY element selector count.')
    choices=[]
    for index in range(count):
        length=a.window_message(combo,0x0149,index)
        if not 0<=length<=512:raise BridgeError('Unsupported ARRAY element selector text.')
        value=ctypes.create_unicode_buffer(length+1)
        a.window_message(combo,0x0148,index,ctypes.addressof(value));choices.append(value.value)
    selected=a.window_message(combo,0x0147)
    if not 0<=selected<count or a.control_text(combo)!=choices[selected]:
        raise BridgeError('ARRAY element selection and actual control text differ.')
    values=[a.control_text(controls[('Edit',cid,None)]) for cid in (2819,2820)]
    limits=[a.window_message(controls[('Edit',cid,None)],0x00D5) for cid in (2819,2820)]
    if any(limit<=0 for limit in limits):raise BridgeError('ARRAY edit control returned an unknown text limit.')
    return controls,choices,limits,dict(element_type=choices[selected],dimensions=values,two_dimensional=bool(two))


def confirm_array_string_length(adapter,array_dialog,length,expected_parent_state,expected_default=128):
    """Resume only the observed STRING child owned by a known ARRAY modal."""
    if type(length) is not int or length<=0 or type(expected_default) is not int or expected_default<=0:
        raise BridgeError('ARRAY STRING length requires an explicit positive integer.')
    expected=_state(expected_parent_state)
    if expected['element_type']!='STRING':raise BridgeError('ARRAY STRING parent checkpoint must select STRING.')
    expected=dict(expected,dimensions=[str(value) for value in expected['dimensions']])
    a=adapter;process=_process(a);binding=(a.pid,a.main,a.program_window,a.project,a.program)
    _bind(a.user.GetWindow,[a.types.HWND,ctypes.c_uint],a.types.HWND)
    _bind(a.user.GetDlgCtrlID,[a.types.HWND],ctypes.c_int)
    def identity():
        if ((a.pid,a.main,a.program_window,a.project,a.program)!=binding or _process(a)!=process
                or not a.user.IsWindow(a.main) or a.window_pid(a.main)!=a.pid
                or not a.title_matches(a.text(a.main)) or a.user.IsWindowEnabled(a.main)
                or not a.user.IsWindow(a.program_window) or a.window_pid(a.program_window)!=a.pid
                or not a.user.IsChild(a.main,a.program_window)
                or not a.program_title_matches(a.text(a.program_window))):
            raise BridgeError('ARRAY STRING project/program/process-start identity changed.')
    def dialogs():
        found=[]
        @a.callback_type
        def visit(hwnd,unused):
            if a.window_pid(hwnd)==a.pid and a.user.IsWindowVisible(hwnd) and a.class_name(hwnd)=='#32770':found.append(hwnd)
            return True
        if not a.user.EnumWindows(visit,0):raise BridgeError('Cannot enumerate ARRAY STRING modal chain.')
        return found
    def parent():
        identity()
        if (not a.user.IsWindow(array_dialog) or not a.user.IsWindowVisible(array_dialog)
                or a.window_pid(array_dialog)!=a.pid or a.class_name(array_dialog)!='#32770'
                or a.text(array_dialog)!='定义数组' or a.user.GetWindow(array_dialog,4)!=a.main):
            raise BridgeError('ARRAY STRING parent modal identity/owner differs.')
        values=_parent_controls(a,array_dialog)
        if values[3]!=expected:raise BridgeError('ARRAY STRING parent differs from the exact checkpoint.')
        return values
    parent_baseline=parent();current=dialogs()
    children=[hwnd for hwnd in current if hwnd!=array_dialog]
    if len(current)!=2 or len(children)!=1:raise BridgeError('Expected exact ARRAY plus owned STRING modal chain.')
    child=children[0];expected_controls={('Button',1,'确定'),('Button',2,'取消'),('Static',-1,'长度：'),('Edit',3023,None)}
    wanted=str(expected_default)
    def inspect():
        if (parent()!=parent_baseline or a.user.IsWindowEnabled(array_dialog)
                or set(dialogs())!={array_dialog,child} or not a.user.IsWindow(child)
                or a.window_pid(child)!=a.pid or a.class_name(child)!='#32770'
                or a.text(child)!='定义字符串' or not a.user.IsWindowEnabled(child)
                or a.user.GetWindow(child,4)!=array_dialog):
            raise BridgeError('Only the exact ARRAY-owned STRING child is supported.')
        controls={};direct=a.children(child)
        if len(direct)!=4:raise BridgeError('ARRAY STRING child must have four observed direct controls.')
        for handle in direct:
            cls=a.class_name(handle);key=(cls,a.user.GetDlgCtrlID(handle),a.text(handle) if cls!='Edit' else None)
            if (key not in expected_controls or key in controls or a.window_pid(handle)!=a.pid
                    or a.user.GetParent(handle)!=child or not a.user.IsWindowVisible(handle)
                    or not a.user.IsWindowEnabled(handle)):
                raise BridgeError('ARRAY STRING child control identity/text/state differs.')
            controls[key]=handle
        edit=controls[('Edit',3023,None)];limit=a.window_message(edit,0x00D5)
        if limit<=0 or a.control_text(edit)!=wanted:raise BridgeError('ARRAY STRING length baseline or edit limit differs.')
        return controls,limit
    controls,limit=inspect();evidence=dict(status='array_string_length_prepared',array_dialog=array_dialog,
        string_dialog=child,process=process,length=length,expected_default=expected_default,
        expected_parent_state=expected_parent_state,confirmation_dispatched_once=False)
    a.last_array_string_length=evidence
    if len(str(length))>limit:raise BridgeError('ARRAY STRING length exceeds the actual edit control limit.')
    if length!=expected_default:
        payload=ctypes.create_unicode_buffer(str(length))
        if not a.window_message(controls[('Edit',3023,None)],0x000C,0,ctypes.addressof(payload)):
            raise BridgeError('ARRAY STRING length editor rejected text.')
        wanted=str(length)
    if inspect()!=(controls,limit):raise BridgeError('ARRAY STRING controls changed before confirmation.')
    a.post(child,0x0111,1);evidence['confirmation_dispatched_once']=True
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        if parent()!=parent_baseline:raise BridgeError('ARRAY parent fields changed after STRING confirmation.')
        current=dialogs()
        if any(hwnd not in (array_dialog,child) for hwnd in current):
            raise BridgeError('Unexpected modal after ARRAY STRING confirmation; do not repeat.')
        if a.user.IsWindow(child) and (a.window_pid(child)!=a.pid or a.class_name(child)!='#32770'
                or a.text(child)!='定义字符串' or a.user.GetWindow(child,4)!=array_dialog):
            raise BridgeError('ARRAY STRING child identity changed after confirmation; do not repeat.')
        if current==[array_dialog] and a.user.IsWindowEnabled(array_dialog):break
        time.sleep(0.05)
    else:raise BridgeError('ARRAY STRING confirmation timed out; it may have completed, do not repeat.')
    evidence['status']='array_string_length_confirmed'
    return evidence


def confirm_array_definition(adapter, element_type, dimensions, expected_state=None, *, string_length=128):
    """Configure one known modal and dispatch IDOK once.

    dimensions=[n] or [n,m] describes the requested controls, not a claimed
    native array encoding. expected_state is an exact, explicit checkpoint for
    an already observed in-flight modal; its dimensions always include both
    edits, including the disabled second edit. No wildcard baseline or retry.
    """
    if (not isinstance(element_type,str) or not element_type or len(element_type)>512
            or any(ord(c)<32 for c in element_type)
            or not isinstance(dimensions,(list,tuple)) or len(dimensions) not in (1,2)
            or any(type(value) is not int or value<=0 for value in dimensions)
            or type(string_length) is not int or string_length<=0
            or (element_type!='STRING' and string_length!=128)):
        raise BridgeError('ARRAY requires an explicit element type and one or two positive integer dimensions.')
    baseline=_state(expected_state if expected_state is not None else
                    dict(element_type='BOOL',dimensions=[1,1],two_dimensional=False))
    a=adapter
    _bind(a.user.GetWindow,[a.types.HWND,ctypes.c_uint],a.types.HWND)
    _bind(a.user.GetDlgCtrlID,[a.types.HWND],ctypes.c_int)
    binding=(a.pid,a.main,a.program_window,a.project,a.program)
    process=_process(a)

    def identity():
        if ((a.pid,a.main,a.program_window,a.project,a.program)!=binding
                or not a.user.IsWindow(a.main) or a.window_pid(a.main)!=a.pid
                or not a.title_matches(a.text(a.main))
                or not a.user.IsWindow(a.program_window) or a.window_pid(a.program_window)!=a.pid
                or not a.user.IsChild(a.main,a.program_window)
                or not a.program_title_matches(a.text(a.program_window)) or _process(a)!=process):
            raise BridgeError('ARRAY dialog project/program/process-start identity changed.')

    def dialogs():
        found=[]
        @a.callback_type
        def visit(hwnd,unused):
            if (a.window_pid(hwnd)==a.pid and a.user.IsWindowVisible(hwnd)
                    and a.class_name(hwnd)=='#32770'):found.append(hwnd)
            return True
        if not a.user.EnumWindows(visit,0):raise BridgeError('Cannot enumerate ARRAY modal windows.')
        return found

    expected={('Edit',2819,None),('ComboBox',1408,None),('Button',1,'确定'),('Button',2,'取消'),
              ('Static',-1,'类型'),('Static',-1,'一维'),('Button',3143,'二维'),('Edit',2820,None)}

    def inspect(dialog):
        identity()
        if (dialogs()!=[dialog] or not a.user.IsWindow(dialog) or a.window_pid(dialog)!=a.pid
                or a.class_name(dialog)!='#32770' or a.text(dialog)!='定义数组'
                or not a.user.IsWindowEnabled(dialog) or a.user.IsWindowEnabled(a.main)
                or a.user.GetWindow(dialog,4)!=a.main):
            raise BridgeError('Only the exact target-owned Define Array modal is supported.')
        controls={};children=a.children(dialog)
        if len(children)!=8:raise BridgeError('ARRAY dialog must have the observed eight direct controls.')
        for child in children:
            cls,cid=a.class_name(child),a.user.GetDlgCtrlID(child)
            label=a.text(child) if cls in ('Button','Static') else None
            key=(cls,cid,label)
            if (key not in expected or key in controls or a.window_pid(child)!=a.pid
                    or a.user.GetParent(child)!=dialog or not a.user.IsWindowVisible(child)):
                raise BridgeError('ARRAY dialog control identity/text/parent differs.')
            controls[key]=child
        two=a.window_message(controls[('Button',3143,'二维')],0x00F0)
        if two not in (0,1):raise BridgeError('ARRAY dimension checkbox has an unknown state.')
        for key,child in controls.items():
            enabled=bool(a.user.IsWindowEnabled(child))
            if enabled!=(bool(two) if key==('Edit',2820,None) else True):
                raise BridgeError('ARRAY dialog control enabled state differs.')
        for cid,label in ((1,'确定'),(2,'取消')):
            if a.window_message(controls[('Button',cid,label)],0x00F0)!=0:
                raise BridgeError('ARRAY confirmation button check state differs.')
        combo=controls[('ComboBox',1408,None)];count=a.window_message(combo,0x0146)
        if not 1<=count<=4096:raise BridgeError('Unsupported ARRAY element selector count.')
        choices=[]
        for index in range(count):
            length=a.window_message(combo,0x0149,index)
            if not 0<=length<=512:raise BridgeError('Unsupported ARRAY element selector text.')
            value=ctypes.create_unicode_buffer(length+1)
            a.window_message(combo,0x0148,index,ctypes.addressof(value));choices.append(value.value)
        selected=a.window_message(combo,0x0147)
        if not 0<=selected<count or a.control_text(combo)!=choices[selected]:
            raise BridgeError('ARRAY element selection and actual control text differ.')
        dimensions_text=[a.control_text(controls[('Edit',cid,None)]) for cid in (2819,2820)]
        limits=[a.window_message(controls[('Edit',cid,None)],0x00D5) for cid in (2819,2820)]
        if any(limit<=0 for limit in limits):raise BridgeError('ARRAY edit control returned an unknown text limit.')
        return controls,choices,limits,dict(element_type=choices[selected],dimensions=dimensions_text,two_dimensional=bool(two))

    identity();current=dialogs()
    if len(current)!=1:raise BridgeError('Expected exactly one ARRAY definition modal.')
    dialog=current[0];controls,choices,limits,observed=inspect(dialog)
    working=dict(element_type=baseline['element_type'],dimensions=[str(n) for n in baseline['dimensions']],
                 two_dimensional=baseline['two_dimensional'])
    if observed!=working:raise BridgeError('ARRAY dialog differs from the exact expected baseline; inspect the in-flight state.')
    if choices.count(element_type)!=1 or choices.count(baseline['element_type'])!=1:
        raise BridgeError('ARRAY element type is unavailable or ambiguous in the actual selector.')
    requested=[str(n) for n in dimensions]
    if any(len(value)>limits[index] for index,value in enumerate(requested)):
        raise BridgeError('ARRAY dimension text exceeds the actual edit control limit.')
    evidence=dict(status='array_definition_prepared',dialog=dialog,process=process,
                  main=a.main,program_window=a.program_window,expected_state=baseline,
                  element_type=element_type,dimensions=list(dimensions),choices=list(choices),
                  control_handles={str(key):value for key,value in controls.items()},text_limits=limits,
                  confirmation_dispatched_once=False)
    a.last_array_definition=evidence

    if working['element_type']==element_type=='STRING' and string_length!=128:
        confirmation=getattr(a,'last_array_string_length',{})
        if (confirmation.get('status')!='array_string_length_confirmed'
                or confirmation.get('array_dialog')!=dialog or confirmation.get('process')!=process
                or confirmation.get('length')!=string_length):
            raise BridgeError('Explicit ARRAY STRING capacity resume requires its exact confirmed child checkpoint; no selection was replayed.')
        evidence['string_length_confirmation']=confirmation

    def unchanged():
        fresh,new_choices,new_limits,state=inspect(dialog)
        if fresh!=controls or new_choices!=choices or new_limits!=limits or state!=working:
            raise BridgeError('ARRAY dialog changed outside the verified field update; do not repeat.')

    two=len(dimensions)==2
    if working['two_dimensional']!=two:
        unchanged();a.window_message(controls[('Button',3143,'二维')],0x00F5)  # BM_CLICK, normal notification.
        working['two_dimensional']=two;unchanged()
    if working['element_type']!=element_type:
        unchanged();a.window_message(controls[('ComboBox',1408,None)],0x014E,choices.index(element_type))
        working['element_type']=element_type;unchanged()
        # CB_SETCURSEL updates the control but does not notify its parent.
        # The normal dialog keeps its own selected element type; dispatch the
        # exact CBN_SELCHANGE once, only to this verified owning modal.
        if element_type=='STRING':
            # This selection enters a native nested modal. A synchronous
            # SendMessage would remain blocked until that modal closes. Queue
            # exactly the normal notification, including the real combo HWND.
            _bind(a.user.PostMessageW,[a.types.HWND,a.types.UINT,a.types.WPARAM,a.types.LPARAM],a.types.BOOL)
            if not a.user.PostMessageW(dialog,0x0111,1408 | (1 << 16),controls[('ComboBox',1408,None)]):
                raise BridgeError('ARRAY STRING selection notification failed; inspect, do not repeat.')
            evidence['selection_change_dispatched_once']=True
            deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                identity();current=dialogs()
                if dialog not in current:raise BridgeError('ARRAY parent disappeared during STRING selection; do not repeat.')
                if any(hwnd!=dialog for hwnd in current):
                    parent_state=dict(working,dimensions=[int(value) for value in working['dimensions']])
                    evidence['string_length_confirmation']=confirm_array_string_length(
                        a,dialog,string_length,parent_state)
                    break
                if _parent_controls(a,dialog)!=(controls,choices,limits,working):
                    raise BridgeError('ARRAY fields changed while awaiting STRING child; do not repeat.')
                time.sleep(0.05)
            else:raise BridgeError('ARRAY STRING child did not appear; inspect the partial modal, do not repeat.')
        else:
            a.window_message(dialog,0x0111,1408 | (1 << 16),controls[('ComboBox',1408,None)])
        unchanged()
    for index,value in enumerate(requested):
        if working['dimensions'][index]==value:continue
        unchanged();payload=ctypes.create_unicode_buffer(value)
        if not a.window_message(controls[('Edit',(2819,2820)[index],None)],0x000C,0,ctypes.addressof(payload)):
            raise BridgeError('ARRAY dimension text editor rejected text; inspect the partial modal.')
        working['dimensions'][index]=value;unchanged()
    unchanged();evidence['confirmed_state']=dict(working,dimensions=list(working['dimensions']))
    a.post(dialog,0x0111,1)
    evidence['confirmation_dispatched_once']=True
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        identity();current=dialogs()
        if any(hwnd!=dialog for hwnd in current):
            raise BridgeError('Unexpected modal after ARRAY confirmation (including STRING length); do not repeat.')
        if a.user.IsWindow(dialog) and (a.window_pid(dialog)!=a.pid or a.class_name(dialog)!='#32770'
                                       or a.text(dialog)!='定义数组'):
            raise BridgeError('ARRAY confirmation left a changed or unknown modal; do not repeat.')
        if a.user.IsWindowEnabled(a.main) and not current and (not a.user.IsWindow(dialog) or not a.user.IsWindowVisible(dialog)):
            break
        time.sleep(0.05)
    else:raise BridgeError('ARRAY confirmation timed out; it may have completed, do not repeat.')
    a.validate_main();a.assert_no_cell_edit()
    evidence['status']='array_definition_confirmed'
    return evidence
