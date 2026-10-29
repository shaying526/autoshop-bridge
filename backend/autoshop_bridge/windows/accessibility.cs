// System MSAA bridge. No clipboard, global input, injection or process memory.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using Accessibility;

public static class BridgeAccessibility {
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr h);
 [DllImport("user32.dll")] static extern bool IsWindowEnabled(IntPtr h);
 [DllImport("user32.dll")] static extern bool IsChild(IntPtr p,IntPtr h);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h,uint m,UIntPtr w,IntPtr l);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern IntPtr SendMessageTimeout(IntPtr h,uint m,UIntPtr w,IntPtr l,uint flags,uint timeout,out UIntPtr result);
 [DllImport("user32.dll")] static extern bool ScreenToClient(IntPtr h,ref Point p);
 [StructLayout(LayoutKind.Sequential)] struct Point {public int X,Y;}
 [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr h,uint id,ref Guid iid,[MarshalAs(UnmanagedType.Interface)]out IAccessible obj);
 [DllImport("oleacc.dll")] static extern int AccessibleChildren(IAccessible o,int start,int count,[Out,MarshalAs(UnmanagedType.LPArray,SizeParamIndex=2)]object[] children,out int obtained);
 sealed class Node {
  public IAccessible Object; public object Id;
  public Node(IAccessible o,object id){Object=o;Id=id;}
  public string Name{get{return Object.get_accName(Id)??"";}}
  public string Value{get{return Object.get_accValue(Id)??"";}}
  public int Role{get{return Convert.ToInt32(Object.get_accRole(Id));}}
  public int State{get{return Convert.ToInt32(Object.get_accState(Id));}}
  IAccessible Client(){return (int)Id==0?Object:Object.get_accChild(Id) as IAccessible;}
  public int ChildCount{get{IAccessible obj=Client();return obj==null?0:obj.accChildCount;}}
  public Node ChildAt(int index){
   IAccessible obj=Client();
   if(obj==null || index<0 || index>=obj.accChildCount)throw new Exception("Child index is outside bounds");
   object[] items=new object[1];int got;
   Marshal.ThrowExceptionForHR(AccessibleChildren(obj,index,1,items,out got));
   if(got!=1)throw new Exception("Accessibility child enumeration is incomplete");
   if(items[0] is IAccessible)return new Node((IAccessible)items[0],0);
   if(items[0] is int)return new Node(obj,items[0]);
   throw new Exception("Unsupported accessibility child");
  }
  public List<Node> Children(){
   IAccessible obj=(int)Id==0?Object:Object.get_accChild(Id) as IAccessible;
   List<Node> list=new List<Node>();if(obj==null)return list;
   int count=obj.accChildCount;if(count<0 || count>10000)throw new Exception("Unexpected accessibility child count");
   object[] items=new object[count];int got;Marshal.ThrowExceptionForHR(AccessibleChildren(obj,0,count,items,out got));
   for(int i=0;i<got;i++) {
    if(items[i] is IAccessible)list.Add(new Node((IAccessible)items[i],0));
    else if(items[i] is int)list.Add(new Node(obj,items[i]));
   }
   return list;
  }
 }
 static string Text(IntPtr h){StringBuilder b=new StringBuilder(8192);GetWindowText(h,b,b.Capacity);return b.ToString();}
 static string Class(IntPtr h){StringBuilder b=new StringBuilder(256);GetClassName(h,b,b.Capacity);return b.ToString();}
 static Node Root(IntPtr h){Guid iid=new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");IAccessible o;Marshal.ThrowExceptionForHR(AccessibleObjectFromWindow(h,0xfffffffc,ref iid,out o));return new Node(o,0);}
 static UIntPtr Message(IntPtr h,uint m,UIntPtr w,IntPtr l){UIntPtr value;if(SendMessageTimeout(h,m,w,l,2,1500,out value)==IntPtr.Zero)throw new Exception("Control message timed out");return value;}
 static void Validate(IntPtr main,IntPtr target,int pid,string project,string program,bool tree){
  uint p;GetWindowThreadProcessId(main,out p);if(p!=pid)throw new Exception("Main process changed");
  GetWindowThreadProcessId(target,out p);if(p!=pid || !IsChild(main,target))throw new Exception("Target process/parent changed");
  string title=Text(main);
  if(!title.StartsWith("AutoShop ",StringComparison.OrdinalIgnoreCase) ||
    !(title.EndsWith("  "+project,StringComparison.OrdinalIgnoreCase) || title.IndexOf("  "+project+" - [",StringComparison.OrdinalIgnoreCase)>=0))throw new Exception("Project title changed");
  if(!IsWindowEnabled(main))throw new Exception("AutoShop modal dialog is open");
  if(tree){
   if(Class(target)!="SysTreeView32")throw new Exception("Expected project tree");
   bool pane=false;for(IntPtr a=GetParent(target);a!=IntPtr.Zero && a!=main;a=GetParent(a))if(Text(a)=="\u5de5\u7a0b\u7ba1\u7406")pane=true;
   if(!pane)throw new Exception("Tree is outside project management pane");
  }else{
   if(Class(target)!="VSFlexGrid8N")throw new Exception("Unsupported variable grid");
   bool match=false;for(IntPtr a=GetParent(target);a!=IntPtr.Zero && a!=main;a=GetParent(a)){
    if(Class(GetParent(a))=="MDIClient" && (Text(a)==program || Text(a)==program+"*" || Text(a)==program+" *"))match=true;
   }
   if(!match)throw new Exception("Grid is outside requested program");
  }
 }
 sealed class GridSource:IBridgeGridSource {
  readonly Node root;readonly Dictionary<int,Node> children=new Dictionary<int,Node>();
  readonly Dictionary<long,Node> cells=new Dictionary<long,Node>();
  public GridSource(Node root){this.root=root;}
  public int ChildCount{get{return root.ChildCount;}}
  Node Child(int index){Node n;if(!children.TryGetValue(index,out n)){n=root.ChildAt(index);children.Add(index,n);}return n;}
  public Node Cell(int child,int column){
   long key=((long)child<<32)|(uint)column;Node n;
   if(!cells.TryGetValue(key,out n)){n=Child(child).ChildAt(column);cells.Add(key,n);}return n;
  }
  public int Role(int child){return Child(child).Role;}
  public string Name(int child){return Child(child).Name;}
  public int CellCount(int child){return Child(child).ChildCount;}
  public int CellRole(int child,int column){return Cell(child,column).Role;}
  public string CellName(int child,int column){return Cell(child,column).Name;}
  public string Value(int child,int column){return Cell(child,column).Value;}
 }
 static void TreeFind(Node n,string program,List<Node> found,int depth,ref int count){
  if(depth>32 || ++count>10000)throw new Exception("Project tree exceeds bounds");
  if(n.Role==36 && n.Name==program)found.Add(n);
  foreach(Node c in n.Children())TreeFind(c,program,found,depth+1,ref count);
 }
 static void CollectTreeNames(Node n,List<string> names,int depth,ref int count){
  if(depth>32 || ++count>10000)throw new Exception("Project tree exceeds bounds");
  if(n.Role==36)names.Add(n.Name);
  foreach(Node c in n.Children())CollectTreeNames(c,names,depth+1,ref count);
 }
 static void InventoryTreeItems(IntPtr target,Node root,UIntPtr item,UIntPtr parentItem,int parent,int depth,List<object> nodes,HashSet<ulong> seen){
  while(item!=UIntPtr.Zero){
   if(depth>32 || nodes.Count>=10000 || !seen.Add(item.ToUInt64()))throw new Exception("Project tree traversal exceeds bounds or repeats an item");
   IntPtr handle=new IntPtr(unchecked((long)item.ToUInt64()));
   if(Message(target,0x110a,new UIntPtr(3),handle)!=parentItem)throw new Exception("Project tree parent changed during traversal");
   UIntPtr mapped=Message(target,0x112b,item,IntPtr.Zero);ulong id=mapped.ToUInt64();
   if(id==0 || id>Int32.MaxValue)throw new Exception("Project tree accessibility mapping is unavailable");
   Node node=new Node(root.Object,(int)id);int role=node.Role;
   if(role!=36)throw new Exception("Project tree item has an unsupported accessibility role");
   int index=nodes.Count;
   nodes.Add(new Dictionary<string,object>{{"index",index},{"parent",parent},{"depth",depth},{"name",node.Name},{"role",role},{"state",node.State},{"accessibility_id",(int)id}});
   UIntPtr child=Message(target,0x110a,new UIntPtr(4),handle);
   InventoryTreeItems(target,root,child,item,index,depth+1,nodes,seen);
   item=Message(target,0x110a,new UIntPtr(1),handle);
  }
 }
 static void Click(IntPtr target,Node cell,bool twice){
  int x,y,w,h;cell.Object.accLocation(out x,out y,out w,out h,cell.Id);
  if(w<=2 || h<=2 || (cell.State&0x18000)!=0)throw new Exception("Target node/cell is offscreen; reveal it first");
  int sx=x+w/2,sy=y+h/2;
  int gx,gy,gw,gh;Node gridRoot=Root(target);gridRoot.Object.accLocation(out gx,out gy,out gw,out gh,0);
  if(sx<gx || sy<gy || sx>=gx+gw || sy>=gy+gh)throw new Exception("Target geometry outside control");
  object hit=Root(target).Object.accHitTest(sx,sy);
  IAccessible hitObject=hit as IAccessible;
  // This grid reports its row/root for hit tests, not the cell. Its actual
  // selected-cell state must be checked in a subsequent request before F2.
  if(twice && hitObject==null) {
   if(!(hit is int))throw new Exception("Cannot verify hit test");
   Node hitNode=new Node(Root(target).Object,hit);
   if(hitNode.Name!=cell.Name)throw new Exception("Hit test identity mismatch");
  }else if(twice){
   Node hitNode=new Node(hitObject,0);
   if(hitNode.Name!=cell.Name || (!twice && hitNode.Value!=cell.Value))throw new Exception("Hit test identity/value mismatch");
  }
  Point p=new Point{X=sx,Y=sy};if(!ScreenToClient(target,ref p) || p.X<0 || p.Y<0 || p.X>32767 || p.Y>32767)throw new Exception("Invalid target geometry");
  IntPtr pos=new IntPtr(p.X|(p.Y<<16));
  uint[] messages=twice?new uint[]{0x201,0x202,0x203,0x202}:new uint[]{0x201,0x202};
  foreach(uint msg in messages)if(!PostMessage(target,msg,new UIntPtr(msg==0x202?0u:1u),pos))throw new Exception("Targeted click post failed");
 }
 static List<Node> FindCells(Node root,string variable,string column,string expected,out BridgeGridReader.CellAddress address){
  GridSource source=new GridSource(root);
  address=BridgeGridReader.Find(source,variable,column,expected);
  // Find validates the logical declaration value. Geometry and selected state
  // must use its name-joined physical row, whose left-side Value may be blank.
  return new List<Node>{source.Cell(address.DisplayChild,address.Column)};
 }
 static Node RevealCell(IntPtr target,string variable,string column,string expected){
  Node root=Root(target);BridgeGridReader.CellAddress address;
  List<Node> found=FindCells(root,variable,column,expected,out address);
  int count=root.ChildCount;
  for(int i=0;i<64;i++) {
   if(i>0){
    root=Root(target);GridSource source=new GridSource(root);
    if(root.ChildCount!=count)throw new Exception("Grid size changed while revealing cell");
    Node value=source.Cell(address.Child,address.Column);
    string key=variable.StartsWith("#row:",StringComparison.Ordinal)?"":variable;
    if(value.Name!=column || value.Value!=expected || source.Cell(address.Child,address.KeyColumn).Value!=key)throw new Exception("Declaration changed during reveal");
    if(address.FullNameColumn>=0 && source.Cell(address.DisplayChild,address.FullNameColumn).Value!=key)throw new Exception("Physical row identity changed during reveal");
    found=new List<Node>{source.Cell(address.DisplayChild,address.Column)};
   }
   if(found.Count!=1)throw new Exception("Cell changed during reveal");
   Node cell=found[0];
   int x,y,w,h,gx,gy,gw,gh;cell.Object.accLocation(out x,out y,out w,out h,cell.Id);root.Object.accLocation(out gx,out gy,out gw,out gh,0);
   if(gh<=20)throw new Exception("Variable declaration area is collapsed or too short to show data rows; expand the declaration pane before editing. grid=["+gx+","+gy+","+gw+","+gh+"], cell=["+x+","+y+","+w+","+h+"]");
   int sx=x+w/2,sy=y+h/2;
   if(w>2 && h>2 && sx>=gx && sx<gx+gw && sy>=gy+20 && sy<gy+gh && (cell.State&0x18000)==0)return cell;
   if(w<=2 || h<=2)throw new Exception("Variable column is hidden");
   if(sx<gx || sx>=gx+gw)Message(target,0x114,new UIntPtr(sx<gx?0u:1u),IntPtr.Zero);
   else {
    // ActiveX consumes wheel input itself rather than outer WM_VSCROLL.
    int packed=((gx+gw/2)&0xffff)|(((gy+gh/2)&0xffff)<<16);
    uint wheel=sy<gy+20?0x00780000u:0xff880000u;
    Message(target,0x20a,new UIntPtr(wheel),new IntPtr(packed));
   }
   System.Threading.Thread.Sleep(20);
  }
  throw new Exception("Could not reveal variable cell by targeted scrolling");
 }
 static bool VisibleSelection(int state,int x,int y,int w,int h,int gx,int gy,int gw,int gh){
  int sx=x+w/2,sy=y+h/2;
  return (state&2)!=0 && (state&0x18000)==0 && w>2 && h>2 && sx>=gx && sx<gx+gw && sy>=gy+20 && sy<gy+gh;
 }
 static void WaitForSelection(Func<bool> check,int milliseconds){
  if(milliseconds<1 || milliseconds>4000)throw new ArgumentOutOfRangeException("milliseconds");
  Stopwatch selected=Stopwatch.StartNew();
  do{
   if(check())return;
   System.Threading.Thread.Sleep(20);
  }while(selected.ElapsedMilliseconds<milliseconds);
  throw new Exception("Requested cell is not actually selected before timeout");
 }
 static readonly string[] InitialColumns={"变量名","初始值","类型","注释","全名","软元件地址","分配地址"};
 static List<Dictionary<string,string>> InitialRows(IntPtr main,IntPtr target,int pid,string project,string instance){
  uint actual;GetWindowThreadProcessId(main,out actual);if(actual!=pid)throw new Exception("Initial-value main process changed");
  GetWindowThreadProcessId(target,out actual);
  string title=Text(main);
  if(actual!=pid || !IsChild(main,target) || Class(target)!="VSFlexGrid8N" || !IsWindowEnabled(main) ||
   !title.StartsWith("AutoShop V4.11.0.5  ",StringComparison.Ordinal) || title.IndexOf("  "+project+" - [",StringComparison.OrdinalIgnoreCase)<0)throw new Exception("Initial-value project/control differs");
  bool toolbox=false;for(IntPtr p=GetParent(target);p!=IntPtr.Zero && p!=main;p=GetParent(p))if(Text(p)=="工具箱")toolbox=true;
  if(!toolbox)throw new Exception("Initial-value grid is outside toolbox");
  Node root=Root(target);int count=root.ChildCount,offset=InitialColumns.Length;
  if(count<offset+2 || count>offset+4097)throw new Exception("Unsupported initial-value row count");
  for(int c=0;c<offset;c++)if(root.ChildAt(c).Role!=25 || root.ChildAt(c).Name!=InitialColumns[c])throw new Exception("Initial-value columns differ");
  var rows=new List<Dictionary<string,string>>();var fullNames=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  for(int i=offset;i<count;i++){
   Node row=root.ChildAt(i);if(row.Role!=28 || row.ChildCount!=offset)throw new Exception("Initial-value row differs");
   var values=new Dictionary<string,string>();
   for(int c=0;c<offset;c++){Node cell=row.ChildAt(c);if(cell.Role!=29 || cell.Name!=InitialColumns[c])throw new Exception("Initial-value cell differs");values[InitialColumns[c]]=cell.Value;}
   if(i==offset){for(int c=0;c<offset;c++)if(values[InitialColumns[c]]!=InitialColumns[c])throw new Exception("Initial-value header differs");continue;}
   string full=values["全名"];
   if(!fullNames.Add(full) || (rows.Count==0?!String.Equals(full,instance,StringComparison.OrdinalIgnoreCase):
    !(full.StartsWith(instance+".",StringComparison.OrdinalIgnoreCase) || full.StartsWith(instance+"[",StringComparison.OrdinalIgnoreCase))))throw new Exception("Initial-value instance/member identity differs");
   rows.Add(values);
  }
  if(root.ChildCount!=count)throw new Exception("Initial-value rows changed");
  return rows;
 }
 static object InitialRun(string action,IntPtr main,IntPtr target,int pid,string project,string instance,string member,string expected){
  var rows=InitialRows(main,target,pid,project,instance);
  if(action=="instance_initial_read")return new Dictionary<string,object>{{"schema",1},{"scope","selected_instance_initial_members"},{"instance",instance},{"rows",rows}};
  if(action!="instance_initial_select")throw new Exception("Unknown initial-value action");
  int index=-1;string full=instance+"."+member;
  for(int i=1;i<rows.Count;i++)if(String.Equals(rows[i]["全名"],full,StringComparison.OrdinalIgnoreCase)){if(index!=-1)throw new Exception("Ambiguous initial-value member");index=i;}
  if(index<0 || rows[index]["初始值"]!=expected)throw new Exception("Initial-value member baseline differs or is not displayed");
  Node root=Root(target);Node cell=root.ChildAt(InitialColumns.Length+1+index).ChildAt(1);
  for(int attempt=0;attempt<64;attempt++){
   int x,y,w,h,gx,gy,gw,gh;cell.Object.accLocation(out x,out y,out w,out h,cell.Id);root.Object.accLocation(out gx,out gy,out gw,out gh,0);
   int sx=x+w/2,sy=y+h/2;
   if(w>2 && h>2 && sx>=gx && sx<gx+gw && sy>=gy+20 && sy<gy+gh && (cell.State&0x18000)==0)break;
   if(w<=2 || h<=2)throw new Exception("Initial-value column is hidden");
   if(sx<gx || sx>=gx+gw)Message(target,0x114,new UIntPtr(sx<gx?0u:1u),IntPtr.Zero);
   else{int packed=((gx+gw/2)&0xffff)|(((gy+gh/2)&0xffff)<<16);Message(target,0x20a,new UIntPtr(sy<gy+20?0x00780000u:0xff880000u),new IntPtr(packed));}
   System.Threading.Thread.Sleep(20);
   rows=InitialRows(main,target,pid,project,instance);
   if(index>=rows.Count || !String.Equals(rows[index]["全名"],full,StringComparison.OrdinalIgnoreCase) || rows[index]["初始值"]!=expected)throw new Exception("Initial-value member changed during reveal");
   root=Root(target);cell=root.ChildAt(InitialColumns.Length+1+index).ChildAt(1);
  }
  Click(target,cell,false);
  WaitForSelection(delegate{
   var current=InitialRows(main,target,pid,project,instance);
   if(index>=current.Count || !String.Equals(current[index]["全名"],full,StringComparison.OrdinalIgnoreCase) || current[index]["初始值"]!=expected)throw new Exception("Initial-value member changed after selection");
   Node fresh=Root(target).ChildAt(InitialColumns.Length+1+index).ChildAt(1);
   return (fresh.State&2)!=0;
  },4000);
  return "initial_member_selection_verified";
 }
 public static object ReadInstancePage(long mainValue,long targetValue,int pid,string project,string program,int offset,int limit){
  IntPtr main=new IntPtr(mainValue),target=new IntPtr(targetValue);
  Validate(main,target,pid,project,program,false);
  object result=BridgeGridReader.ReadInstancePage(new GridSource(Root(target)),offset,limit);
  Validate(main,target,pid,project,program,false);return result;
 }
 public static object Run(string action,long mainValue,long targetValue,int pid,string project,string program,string variable,string column,string expected){
  IntPtr main=new IntPtr(mainValue),target=new IntPtr(targetValue);bool keyboardContext=action=="tree_context_keyboard";
  if(action=="instance_initial_read" || action=="instance_initial_select")return InitialRun(action,main,target,pid,project,variable,column,expected);
  bool tree=action=="open" || action=="tree_context" || keyboardContext || action=="tree_nodes" || action=="tree_inventory";
  Validate(main,target,pid,project,program,tree);Node root=Root(target);
  if(action=="grid_columns"){
   var columns=new List<string>();
   if(root.ChildCount<2 || root.ChildCount>10000)throw new Exception("Unsupported grid size");
   for(int i=0;i<root.ChildCount && root.ChildAt(i).Role==25;i++){
    if(columns.Count>=32)throw new Exception("Too many grid columns");columns.Add(root.ChildAt(i).Name);
   }
   Validate(main,target,pid,project,program,false);
   return new Dictionary<string,object>{{"columns",columns},{"accessible_children",root.ChildCount}};
  }
  if(action=="grid" || action=="grid_display"){
   object result=action=="grid"?BridgeGridReader.Read(new GridSource(root)):BridgeGridReader.ReadDisplayed(new GridSource(root));
   Validate(main,target,pid,project,program,false);return result;
  }
  if(action=="tree_nodes"){
   var names=new List<string>();int count=0;CollectTreeNames(root,names,0,ref count);return names;
  }
  if(action=="tree_inventory"){
   ulong before=Message(target,0x1105,UIntPtr.Zero,IntPtr.Zero).ToUInt64();
   if(before>10000)throw new Exception("Project tree item count exceeds bounds");
   var nodes=new List<object>();var seen=new HashSet<ulong>();
   InventoryTreeItems(target,root,Message(target,0x110a,UIntPtr.Zero,IntPtr.Zero),UIntPtr.Zero,-1,0,nodes,seen);
   Validate(main,target,pid,project,program,true);
   ulong after=Message(target,0x1105,UIntPtr.Zero,IntPtr.Zero).ToUInt64();
   if(before!=after || before!=(ulong)nodes.Count)throw new Exception("Project tree enumeration is incomplete or changed");
   return new Dictionary<string,object>{{"profile","native-tree-items-msaa-v1"},{"complete",true},{"node_count",nodes.Count},{"tree_count_before",before},{"tree_count_after",after},{"includes_collapsed_items",true},{"atomic_snapshot",false},{"nodes",nodes}};
  }
  if(action=="open" || action=="tree_context" || keyboardContext){
   if((action=="tree_context" || keyboardContext) && program!="程序块" && program!="功能块" && program!="数据类型" && program!="全局变量表" && program!="功能块(FB)" && program!="函数(FC)" && program!="结构体" && program!="软元件表" && program!="功能块实例")throw new Exception("Unsupported creation category");
   List<Node> found=new List<Node>();int count=0;TreeFind(root,program,found,0,ref count);
   if(found.Count!=1)throw new Exception("Expected one exact program tree node; found "+found.Count);
   if((int)found[0].Id<=0)throw new Exception("Unsupported tree item identity");
   UIntPtr item=Message(target,0x112a,new UIntPtr((uint)(int)found[0].Id),IntPtr.Zero);
   if(item==UIntPtr.Zero)throw new Exception("Cannot map tree item identity");
   Message(target,0x1114,UIntPtr.Zero,new IntPtr(unchecked((long)item.ToUInt64())));
   UIntPtr selected=Message(target,0x110b,new UIntPtr(9),new IntPtr(unchecked((long)item.ToUInt64())));
   Validate(main,target,pid,project,program,true);
   if(keyboardContext){
    // Selection can be vetoed by TVN_SELCHANGING. Prove the current caret
    // and fresh MSAA identity before requesting a keyboard context menu.
    if(selected==UIntPtr.Zero)throw new Exception("Creation category selection was rejected");
    if(Message(target,0x110a,new UIntPtr(9),IntPtr.Zero)!=item)throw new Exception("Creation category caret differs");
    UIntPtr accessibleId=Message(target,0x112b,item,IntPtr.Zero);
    ulong id=accessibleId.ToUInt64();
    if(id==0 || id>Int32.MaxValue || id!=(uint)(int)found[0].Id)throw new Exception("Creation category accessibility identity changed");
    Node fresh=new Node(Root(target).Object,(int)id);
    if(fresh.Name!=program || (fresh.State&2)==0)throw new Exception("Creation category name/selection readback differs");
    Validate(main,target,pid,project,program,true);
    if(Message(target,0x110a,new UIntPtr(9),IntPtr.Zero)!=item)throw new Exception("Creation category caret changed before context request");
    if(!PostMessage(target,0x007b,new UIntPtr(unchecked((ulong)target.ToInt64())),new IntPtr(-1)))throw new Exception("Keyboard category context request failed");
    return "context_posted";
   }
   if(action=="open"){Click(target,found[0],true);return "open_posted";}
   int x,y,w,h;found[0].Object.accLocation(out x,out y,out w,out h,found[0].Id);
   if(w<=2 || h<=2 || (found[0].State&0x18000)!=0)throw new Exception("Creation category is offscreen");
   Point point=new Point{X=x+w/2,Y=y+h/2};
   if(!ScreenToClient(target,ref point) || point.X<0 || point.Y<0 || point.X>32767 || point.Y>32767)throw new Exception("Invalid category geometry");
   IntPtr position=new IntPtr(point.X|(point.Y<<16));
   if(!PostMessage(target,0x204,new UIntPtr(2),position) || !PostMessage(target,0x205,UIntPtr.Zero,position))throw new Exception("Category context click failed");
   return "context_posted";
  }
  if(action=="select_verified_cell"){
   Node visible=RevealCell(target,variable,column,expected);
   Validate(main,target,pid,project,program,false);
   Click(target,visible,false);
   WaitForSelection(delegate{
    // Fresh lookup after the posted click: no reuse of the selection/value
    // snapshot from before the UI processed that click.
    Validate(main,target,pid,project,program,false);
    BridgeGridReader.CellAddress address;Node currentRoot=Root(target);
    List<Node> cells=FindCells(currentRoot,variable,column,expected,out address);
    if(cells.Count!=1)throw new Exception("Cell baseline/identity mismatch");
    int state=cells[0].State;
    int x,y,w,h,gx,gy,gw,gh;
    cells[0].Object.accLocation(out x,out y,out w,out h,cells[0].Id);
    currentRoot.Object.accLocation(out gx,out gy,out gw,out gh,0);
    if(VisibleSelection(state,x,y,w,h,gx,gy,gw,gh)){
     Validate(main,target,pid,project,program,false);return true;
    }
    return false;
   },4000);
   return "selection_verified";
  }
  if(action=="select_cell" || action=="check_cell" || action=="cell_info"){
   if(action=="select_cell"){Node visible=RevealCell(target,variable,column,expected);Click(target,visible,false);return "selection_posted";}
   BridgeGridReader.CellAddress address;List<Node> cells=FindCells(root,variable,column,expected,out address);
   if(cells.Count!=1)throw new Exception("Cell baseline/identity mismatch");
   if(action=="cell_info"){
    int x,y,w,h,gx,gy,gw,gh;cells[0].Object.accLocation(out x,out y,out w,out h,cells[0].Id);root.Object.accLocation(out gx,out gy,out gw,out gh,0);
    Node row=root.ChildAt(address.Child);int rx,ry,rw,rh;row.Object.accLocation(out rx,out ry,out rw,out rh,row.Id);
    return new Dictionary<string,object>{{"state",cells[0].State},{"rect",new int[]{x,y,w,h}},{"grid",new int[]{gx,gy,gw,gh}},
      {"row_rect",new int[]{rx,ry,rw,rh}},{"row_state",row.State},{"child_index",address.Child},{"display_child_index",address.DisplayChild},{"column_index",address.Column},
      {"logical_value",row.ChildAt(address.Column).Value},{"display_value",cells[0].Value},
      {"display_name",root.ChildAt(address.DisplayChild).ChildAt(address.KeyColumn).Value}};
   }
   if((cells[0].State&2)==0)throw new Exception("Requested cell is not actually selected");
   return "selection_verified";
  }
  throw new Exception("Unknown accessibility action");
 }
}
