param([long]$Main,[long]$Tree,[int]$ProcessId,[string]$Project)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName Accessibility
Add-Type -ReferencedAssemblies Accessibility -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using Accessibility;
public static class CreationTreeContext {
 [DllImport("user32.dll")]static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll")]static extern bool IsChild(IntPtr p,IntPtr h);
 [DllImport("user32.dll")]static extern IntPtr GetParent(IntPtr h);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)]static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)]static extern int GetClassName(IntPtr h,StringBuilder s,int n);
 [DllImport("oleacc.dll")]static extern int AccessibleObjectFromWindow(IntPtr h,uint id,ref Guid iid,[MarshalAs(UnmanagedType.Interface)]out IAccessible o);
 static string Text(IntPtr h,bool cls){var s=new StringBuilder(8192);if(cls)GetClassName(h,s,s.Capacity);else GetWindowText(h,s,s.Capacity);return s.ToString();}
 public static string Read(long m,long t,int pid,string project){
  IntPtr main=new IntPtr(m),tree=new IntPtr(t);uint p;GetWindowThreadProcessId(main,out p);
  if(p!=pid || Text(main,false).IndexOf("  "+project+" - [",StringComparison.OrdinalIgnoreCase)<0)throw new Exception("Project changed");
  GetWindowThreadProcessId(tree,out p);
  if(p!=pid || !IsChild(main,tree) || Text(tree,true)!="SysTreeView32")throw new Exception("Tree changed");
  bool pane=false;for(IntPtr a=GetParent(tree);a!=IntPtr.Zero && a!=main;a=GetParent(a))if(Text(a,false)=="\u5de5\u7a0b\u7ba1\u7406")pane=true;
  if(!pane)throw new Exception("Expected project management tree");
  Guid iid=new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");IAccessible root;
  Marshal.ThrowExceptionForHR(AccessibleObjectFromWindow(tree,0xfffffffc,ref iid,out root));
  object selected=root.accSelection;IAccessible obj=selected as IAccessible;
  object id=obj==null?selected:0;if(obj==null)obj=root;
  if(!(id is int) || Convert.ToInt32(obj.get_accRole(id))!=36)throw new Exception("Expected a single selected tree item");
  return obj.get_accName(id)??"";
 }
}
'@
@{selected_name=[CreationTreeContext]::Read($Main,$Tree,$ProcessId,$Project)}|ConvertTo-Json -Compress
