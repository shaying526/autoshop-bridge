// Pure declaration/monitor layout reader, also exercised with an in-memory source.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text.RegularExpressions;

public interface IBridgeGridSource {
 int ChildCount {get;}
 int Role(int child);
 string Name(int child);
 int CellCount(int child);
 int CellRole(int child,int column);
 string CellName(int child,int column);
 string Value(int child,int column);
}

// Initial-value toolbox slots have their own seven-column physical layout.
// Geometry qualifies empty slots only; offscreen named rows remain evidence.
public interface IBridgeInitialSource:IBridgeGridSource {
 int RowHeight(int child);
 int NameHeight(int child);
}
public static class BridgeInitialGridReader {
 public static readonly string[] Columns={"变量名","初始值","类型","注释","全名","软元件地址","分配地址"};
 public static string RevealDirection(int[] cell,int state,int[] grid,int offset){
  if(cell==null || cell.Length!=4 || grid==null || grid.Length!=4)throw new Exception("Initial reveal requires complete fresh rectangles");
  int x=cell[0],y=cell[1],w=cell[2],h=cell[3],gx=grid[0],gy=grid[1],gw=grid[2],gh=grid[3];
  if(offset==-1)offset=w/2;
  if(offset<1 || offset>=w-1 || h<=2 || gh<=20 || gw<=2)throw new Exception("Initial glyph/cell geometry or pane is unsupported");
  long sx=(long)x+offset,sy=(long)y+h/2;
  if(sx>=gx && sx<(long)gx+gw && sy>=gy+20 && sy<(long)gy+gh && (state&0x18000)==0)return "visible";
  if(sx<gx)return "left";if(sx>=(long)gx+gw)return "right";
  if(sy<gy+20)return "up";if(sy>=(long)gy+gh)return "down";
  // Partially clipped MSAA cells can be INVISIBLE with their glyph inside.
  // A single clipped edge determines the reveal direction; two opposing
  // edges cannot be resolved by repeating or guessing scrolls.
  bool left=x<gx,right=(long)x+w>(long)gx+gw,above=y<gy+20,below=(long)y+h>(long)gy+gh;
  if(left && right)throw new Exception("Initial cell spans both horizontal pane edges");
  if(left)return "left";if(right)return "right";
  if(above && below)throw new Exception("Initial cell spans both vertical data edges");
  if(above)return "up";if(below)return "down";
  throw new Exception("Initial cell is flagged invisible without a clipped edge");
 }
 static void Equal(string[] actual,string[] expected){
  if(expected==null || expected.Length!=7)throw new Exception("Initial checkpoint requires seven complete fields");
  for(int c=0;c<7;c++)if(expected[c]==null || actual[c]!=expected[c])throw new Exception("Initial checkpoint field changed at column "+c);
 }
 static int Frame(IBridgeInitialSource source){
  int count=source.ChildCount;
  if(count<9 || count>4104)throw new Exception("Unsupported initial physical slot count");
  for(int c=0;c<7;c++)if(source.Role(c)!=25 || source.Name(c)!=Columns[c])throw new Exception("Initial columns differ");
  Equal(Row(source,-1),Columns);return count-8;
 }
 static string[] Row(IBridgeInitialSource source,int index){
  int child=8+index;
  if(source.Role(child)!=28 || source.CellCount(child)!=7)throw new Exception("Initial physical row shape differs");
  var row=new string[7];for(int c=0;c<7;c++){
   if(source.CellRole(child,c)!=29 || source.CellName(child,c)!=Columns[c])throw new Exception("Initial cell identity differs");
   row[c]=source.Value(child,c)??"";
  }return row;
 }
 static void Identity(string[] row,string instance,bool root){
  bool blank=true;foreach(string text in row)if(text!="")blank=false;
  if(blank){if(root)throw new Exception("Initial selected root is blank");return;}
  string full=row[4];
  if(row[0]=="" || row[2]=="" || (root?(!String.Equals(row[0],instance,StringComparison.OrdinalIgnoreCase) || !String.Equals(full,instance,StringComparison.OrdinalIgnoreCase)):
   !(full.StartsWith(instance+".",StringComparison.OrdinalIgnoreCase) || full.StartsWith(instance+"[",StringComparison.OrdinalIgnoreCase))))throw new Exception("Initial instance/member identity differs");
 }
 static int[] Heights(IBridgeInitialSource source,int index,string[] row){
  int rh=source.RowHeight(8+index),nh=source.NameHeight(8+index);bool blank=true;
  foreach(string value in row)if(value!="")blank=false;
  if(rh<1 || nh<1 || (blank && (rh!=1 || nh!=1)))throw new Exception("Unknown initial blank/row geometry");
  return new int[]{rh,nh};
 }
 public static object ReadPage(IBridgeInitialSource source,string instance,int offset,int limit){
  if(String.IsNullOrEmpty(instance) || offset<0 || limit<1 || limit>64)throw new Exception("Invalid initial page range/instance");
  int total=Frame(source);if(offset>total)throw new Exception("Initial page offset outside physical slots");
  var root=Row(source,0);Identity(root,instance,true);
  var rows=new List<object>();var values=new List<string[]>();var heights=new List<int[]>();int end=Math.Min(total,offset+limit);
  for(int index=offset;index<end;index++){
   var row=Row(source,index);Identity(row,instance,index==0);var h=Heights(source,index,row);values.Add(row);heights.Add(h);
   rows.Add(new Dictionary<string,object>{{"physical_index",index},{"values",row},{"row_height",h[0]},{"name_height",h[1]}});
  }
  if(Frame(source)!=total)throw new Exception("Initial physical collection changed during page read");Equal(Row(source,0),root);
  if(end>offset)foreach(int index in new int[]{offset,end-1}){
   var row=Row(source,index);Equal(row,values[index-offset]);var h=Heights(source,index,row);
   if(h[0]!=heights[index-offset][0] || h[1]!=heights[index-offset][1])throw new Exception("Initial page boundary geometry changed");
  }
  if(source.ChildCount!=total+8)throw new Exception("Initial count changed after boundary proof");
  return new Dictionary<string,object>{{"schema",1},{"scope","fbi_initial_physical_page"},{"instance",instance},{"columns",(string[])Columns.Clone()},
   {"physical_data_rows",total},{"accessible_children",total+8},{"offset",offset},{"limit",limit},{"root_row",root},{"rows",rows},
   {"boundary_stable",true},{"native_values_used",false}};
 }
 public static string[] Checkpoint(IBridgeInitialSource source,string instance,int total,int index,string[] rootExpected,string[] expected,string[] before,string[] after){
  if(Frame(source)!=total || index<0 || index>=total)throw new Exception("Initial physical checkpoint bounds/count differ");
  var root=Row(source,0);Identity(root,instance,true);Equal(root,rootExpected);
  var row=Row(source,index);Identity(row,instance,index==0);Equal(row,expected);Heights(source,index,row);
  if(index==0){if(before!=null)throw new Exception("Initial preceding boundary must be null");}else Equal(Row(source,index-1),before);
  if(index==total-1){if(after!=null)throw new Exception("Initial following boundary must be null");}else Equal(Row(source,index+1),after);
  if(source.ChildCount!=total+8)throw new Exception("Initial count changed during checkpoint");return row;
 }
}

public static class BridgeGridReader {
 static bool PlainScalar(string type){
  return type=="BOOL" || type=="INT" || type=="DINT" || type=="REAL" || type=="BYTE" || type=="IP";
 }
 public sealed class CellAddress {public int Child;public int Column;public int DisplayChild;public int KeyColumn;public int FullNameColumn;}
 sealed class Layout {
  public IBridgeGridSource Source;public int Count,Offset,Rows,Key,Left;
  public bool Watch;public List<string> Columns=new List<string>();
  public bool Hybrid;
  public bool RequireHybridFrame;
  public bool SystemReadOnly;
  public List<int> DeclarationRows=new List<int>();
  int compactCount;
  int overlapBoundary=-1;
  string[] overlapSnapshot;
  List<int> overlapRoots;
  readonly Dictionary<int,string[]> appended=new Dictionary<int,string[]>();
  readonly Dictionary<int,string> hybridCells=new Dictionary<int,string>();
  int hybridFirstReads,hybridVerificationReads,hybridCacheHits;
  public readonly List<string> AppendedNamedArrayRoots=new List<string>();
  static readonly string[] Global={"序号","变量名","数据类型","隐藏初始值","初始值","掉电保持","网络公开","注释","软元件地址","分配地址","长度","ID","当前值","数据值1","数据值2","数据值3","数据值4","全名称"};
  static readonly string[] Structure={"序号","成员变量名","数据类型","注释","ID"};
  static readonly string[] FB={"序号","类别","名称","数据类型","隐藏初始值","初始值","掉电保持","注释","ID"};
  static readonly string[] FC={"序号","类别","名称","数据类型","注释","ID"};
  static readonly string[] Instances={"序号","变量名","数据类型","隐藏初始值","初始值","注释","分配地址","保持区地址","指针地址","长度","ID"};
  static readonly string[] SystemVariables={"序号","变量名","数据类型","隐藏初始值","初始值","掉电保持","注释"};
  static bool Same(List<string> actual,string[] expected){
   if(actual.Count!=expected.Length)return false;
   for(int i=0;i<expected.Length;i++)if(actual[i]!=expected[i])return false;
   return true;
  }
  public Layout(IBridgeGridSource source){
   Source=source;Count=source.ChildCount;
   if(Count<2 || Count>10000)throw new Exception("Unsupported accessibility grid size");
   while(Offset<Count && source.Role(Offset)==25){
    string name=source.Name(Offset++);
    if(Columns.Contains(name) || Columns.Count>=32)throw new Exception("Duplicate/invalid grid columns");
    Columns.Add(name);
   }
   Watch=Same(Columns,Global);
   SystemReadOnly=Same(Columns,SystemVariables);
   if(!Watch && !SystemReadOnly && !Same(Columns,Structure) && !Same(Columns,FB) && !Same(Columns,FC) && !Same(Columns,Instances))throw new Exception("Unsupported grid column layout");
   Key=(Same(Columns,FB)||Same(Columns,FC))?2:1;Left=Watch?8:Columns.Count;Rows=Count-Offset;
   if(Rows<2)throw new Exception("Grid is missing its declaration boundary");
   for(int c=0;c<Columns.Count;c++)if(Cell(0,c)!=Columns[c])throw new Exception("Grid header differs");
  }
  readonly HashSet<int> checkedRows=new HashSet<int>();
  public string Cell(int row,int column){
   string captured;
   if(Hybrid && hybridCells.TryGetValue(row*32+column,out captured)){hybridCacheHits++;return captured;}
   return ActualCell(row,column);
  }
  string ActualCell(int row,int column){
   if(row<0 || row>=Rows)throw new Exception("Grid row is outside bounds");
   int child=Offset+row;
   if(!checkedRows.Contains(row)){
    if(Source.Role(child)!=28 || Source.CellCount(child)!=Columns.Count)throw new Exception("Unexpected grid row/column count");
    checkedRows.Add(row);
   }
   if(Source.CellRole(child,column)!=29 || Source.CellName(child,column)!=Columns[column])throw new Exception("Grid cell identity differs");
   return Source.Value(child,column)??"";
  }
  public void Blank(int row){
   for(int c=1;c<Left;c++)if(Cell(row,c)!="")throw new Exception("Incomplete declaration boundary");
   string seq=Cell(row,0);
   if(seq!="" && seq!=row.ToString())throw new Exception("Invalid spare-row number");
  }
  public List<string> Declarations(){
   List<string> names=new List<string>();HashSet<string> unique=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
   for(int row=1;row<Rows && row<=4097;row++){
    string name=Cell(row,Key);
    if(name==""){Blank(row);compactCount=names.Count;return names;}
    if(Cell(row,0)!=row.ToString())throw new Exception("Invalid/duplicate declaration row");
    if(!unique.Add(name)){
     // A complete compact cache can run directly into an expanded monitor
     // root, without an intervening blank. This is only a candidate boundary:
     // WatchRoots must prove that every cached name has exactly its ordered
     // root and that no additional declaration remains before the final blank.
     if(!Watch || !names.Contains(name) || Cell(row,Columns.Count-1)!=name)throw new Exception("Invalid/duplicate declaration row");
     overlapBoundary=row;compactCount=names.Count;
     overlapSnapshot=new string[Columns.Count];
     for(int c=0;c<Columns.Count;c++)overlapSnapshot[c]=Cell(row,c);
     return names;
    }
    if(row>4096)throw new Exception("Invalid/duplicate declaration row");
    names.Add(name);
    DeclarationRows.Add(row);
   }
   throw new Exception("Missing declaration boundary or row limit exceeded");
  }
  static bool Member(string full,string name){return full==name || full.StartsWith(name+"[",StringComparison.Ordinal) || full.StartsWith(name+".",StringComparison.Ordinal);}
  public int NextRoot(int row,string name){
   int low=row,high=row+1,step=1;
   // Expanded monitor members form contiguous preorder branches. Probe their
   // ends without constructing thousands of unrelated COM row/cell objects.
   while(high<Rows && Member(Cell(high,Columns.Count-1),name)){
    low=high;step=Math.Min(Rows,step*2);high=Math.Min(Rows,row+step);
   }
   while(high-low>1){
    int mid=low+(high-low)/2;
    if(Member(Cell(mid,Columns.Count-1),name))low=mid;else high=mid;
   }
   return high;
  }
  void CheckOverlapBranches(List<string> names,List<int> roots){
   // The exceptional profile must prove the entire preorder, rather than
   // relying on sparse branch-end probes to conceal an unknown interior root.
   for(int i=0;i<names.Count;i++){
    int end=i+1<roots.Count?roots[i+1]:Rows-1;
    for(int row=roots[i]+1;row<end;row++){
     string full=Cell(row,Columns.Count-1);
     if(full==names[i] || !Member(full,names[i]))throw new Exception("Invalid overlapping monitor branch");
    }
   }
  }
  string OverlapDiagnostic(List<string> names,List<int> roots,int next){
   Func<string,string> bounded=delegate(string value){
    value=value??"";if(value.Length>160)value=value.Substring(0,160)+"...(length="+value.Length+")";
    return value.Replace("\r","\\r").Replace("\n","\\n").Replace("\0","\\0");
   };
   var mapped=new List<string>();for(int i=0;i<Math.Min(32,roots.Count);i++)mapped.Add(roots[i].ToString());
   return "overlap_boundary="+overlapBoundary+"; compact_count="+names.Count+"; physical_rows="+Rows+
    "; boundary_is_mapped_root="+roots.Contains(overlapBoundary)+"; mapped_roots=["+String.Join(",",mapped.ToArray())+"]"+
    "; next_row="+next+"; next_full_name="+(next<Rows?bounded(Cell(next,Columns.Count-1)):"<outside>")+
    "; boundary_name="+bounded(Cell(overlapBoundary,Key))+"; boundary_full_name="+bounded(Cell(overlapBoundary,Columns.Count-1))+
    "; last_full_name="+bounded(Cell(Rows-1,Columns.Count-1));
  }
  string Observed(int row,int column){
   string value;int key=row*32+column;
   if(hybridCells.TryGetValue(key,out value)){hybridCacheHits++;return value;}
   value=ActualCell(row,column);hybridFirstReads++;hybridCells.Add(key,value);
   return value;
  }
  string[] ObservedRow(int row){var values=new string[Columns.Count];for(int c=0;c<values.Length;c++)values[c]=Observed(row,c);return values;}
  sealed class HybridInfo {
   public List<string> Names=new List<string>();public List<int> Roots=new List<int>();
   public Dictionary<string,List<int>> Cache=new Dictionary<string,List<int>>(StringComparer.Ordinal);
   public Dictionary<int,string[]> Records=new Dictionary<int,string[]>();
  }
  static bool HybridMember(string full,string name){return full.StartsWith(name+"[",StringComparison.Ordinal) || full.StartsWith(name+".",StringComparison.Ordinal);}
  static bool RootName(string name){return name!="" && name.IndexOfAny(new char[]{'.','[',']','\r','\n','\0'})<0;}
  static bool BlankLeft(string[] row){for(int c=1;c<8;c++)if(row[c]!="")return false;return true;}
  HybridInfo InspectHybrid(){
   if(!Watch)throw new Exception("Hybrid inventory requires the observed GVT columns");
   for(int c=0;c<Columns.Count;c++)Observed(0,c);
   var info=new HybridInfo();var unique=new HashSet<string>(StringComparer.OrdinalIgnoreCase);string current=null;
   for(int row=1;row<Rows-1;row++){
    string full=Observed(row,Columns.Count-1);
    if(current!=null && HybridMember(full,current))continue;
    if(!RootName(full) || !unique.Add(full))throw new Exception("Hybrid root/order/branch identity differs at physical row "+row);
    info.Names.Add(full);info.Roots.Add(row);current=full;
   }
   if(info.Names.Count>4096)throw new Exception("Hybrid declaration count exceeds observed bounds");
   var final=ObservedRow(Rows-1);
   if(final[0]!="" && final[0]!=(Rows-1).ToString())throw new Exception("Hybrid final spare sequence differs");
   for(int c=1;c<final.Length;c++)if(final[c]!="")throw new Exception("Hybrid final spare is not completely blank");
   var ids=new HashSet<int>();
   foreach(int row in info.Roots){
    var values=ObservedRow(row);info.Records.Add(row,values);string name=values[17];int id;
    if(values[1]!="" && values[1]!=name)throw new Exception("Hybrid physical root name differs from its full name: "+name);
    if(values[0]!="" && values[0]!=row.ToString())throw new Exception("Hybrid physical root sequence differs: "+name);
    if(values[11]!="" && (!Int32.TryParse(values[11],out id) || id<=0 || !ids.Add(id)))throw new Exception("Hybrid physical root ID is invalid or duplicated: "+name);
    if(values[10]!="" && !Regex.IsMatch(values[10],@"\AnBitLen:[1-9][0-9]*\z"))throw new Exception("Hybrid physical root bit length differs: "+name);
   }
   var rootSet=new HashSet<int>(info.Roots);int previousRank=-1;
   for(int row=1;row<=info.Names.Count;row++){
    if(rootSet.Contains(row))continue;
    var values=ObservedRow(row);info.Records.Add(row,values);
    if(BlankLeft(values))continue;
    string name=values[1];int rank=info.Names.IndexOf(name);
    if(rank<0 || values[2]=="" || values[5]=="" || values[6]=="" || values[0]!=row.ToString())
     throw new Exception("Hybrid unmapped or partial compact declaration at physical row "+row);
    if(rank<=previousRank)throw new Exception("Hybrid compact declaration ordering differs");previousRank=rank;
    List<int> sources;if(!info.Cache.TryGetValue(name,out sources)){sources=new List<int>();info.Cache.Add(name,sources);}sources.Add(row);
    string rootId=info.Records[info.Roots[rank]][11];int cached;
    if(values[11]!="" && (!Int32.TryParse(values[11],out cached) || cached<=0 || (rootId!="" && values[11]!=rootId)))
     throw new Exception("Hybrid same-name cache/root ID conflict: "+name);
   }
   return info;
  }
  List<string> MissingRootFields(string[] row){
   var missing=new List<string>();foreach(int c in new int[]{0,1,2,5,6,10,11})if(row[c]=="")missing.Add(Columns[c]);return missing;
  }
  List<int> HybridRoots(List<string> names){
   return ApplyHybrid(InspectHybrid(),names);
  }
  List<int> ApplyHybrid(HybridInfo info,List<string> names){
   for(int i=0;i<info.Roots.Count;i++){
    int physical=info.Roots[i];var missing=MissingRootFields(info.Records[physical]);
    if(missing.Count>0)throw new Exception("HYBRID_ROOT_FIELDS_MISSING: physical_rows="+Rows+"; physical_row="+physical+"; full_name="+info.Names[i]+"; missing="+String.Join(",",missing.ToArray()));
   }
   names.Clear();names.AddRange(info.Names);DeclarationRows.Clear();
   for(int i=0;i<names.Count;i++){
    string name=names[i];int root=info.Roots[i],hidden=root;var values=info.Records[root];List<int> sources;
    bool numeric=PlainScalar(values[2]);
    if(info.Cache.TryGetValue(name,out sources))foreach(int source in sources){
     var cached=info.Records[source];
     foreach(int c in new int[]{1,2,5,6,7})if(cached[c]!=values[c])throw new Exception("Hybrid cache/root declaration field differs: "+name+" column "+c);
     if(!numeric)hidden=source;
     else if(cached[3]!=values[3] || cached[4]!=values[4])throw new Exception("Hybrid numeric cache/root initializer differs: "+name);
    }
    DeclarationRows.Add(hidden);
   }
   Hybrid=true;return info.Roots;
  }
  void StableHybrid(){
   if(Source.ChildCount!=Count)throw new Exception("Hybrid grid count changed during read");
   for(int c=0;c<Columns.Count;c++)if(Source.Role(c)!=25 || Source.Name(c)!=Columns[c])throw new Exception("Hybrid column identity changed during read");
   var checkedShape=new HashSet<int>();
   foreach(var entry in hybridCells){
    int row=entry.Key/32,column=entry.Key%32,child=Offset+row;
    if(checkedShape.Add(row) && (Source.Role(child)!=28 || Source.CellCount(child)!=Columns.Count))throw new Exception("Hybrid row/column count changed at "+row);
    hybridVerificationReads++;
    if(ActualCell(row,column)!=entry.Value)throw new Exception("Hybrid field changed during read at row "+row+", column "+column);
   }
   if(Source.ChildCount!=Count)throw new Exception("Hybrid grid count changed after verification");
  }
  object InventoryFrom(HybridInfo info,bool verified){
   var roots=new List<object>();
   for(int i=0;i<info.Roots.Count;i++){
    int row=info.Roots[i];var missing=MissingRootFields(info.Records[row]);
    roots.Add(new Dictionary<string,object>{{"physical_row",row},{"full_name",info.Names[i]},
     {"row",info.Records[row]},{"before_full_name",Observed(row-1,17)},{"after_full_name",Observed(row+1,17)},
     {"missing_fields",missing},{"complete_root_fields",missing.Count==0}});
   }
   return new Dictionary<string,object>{{"schema",1},{"profile","autoshop-gvt-root-inventory-v1"},
    {"physical_rows",Rows},{"accessible_children",Count},{"columns",Columns},{"roots",roots},
    {"root_preorder_complete",true},{"stable_two_pass",verified},{"atomic_snapshot",false},{"native_values_used",false}};
  }
  public object RootInventory(){HybridInfo info=InspectHybrid();object inventory=InventoryFrom(info,true);StableHybrid();return inventory;}
  public object SingleHybridFrame(){
   HybridInfo info=InspectHybrid();object inventory=InventoryFrom(info,false);bool missing=false;
   foreach(int row in info.Roots)if(MissingRootFields(info.Records[row]).Count!=0)missing=true;
   object grid=null;
   if(!missing){
    var names=new List<string>();ApplyHybrid(info,names);var rows=new List<Dictionary<string,string>>();
    for(int i=0;i<names.Count;i++){
     var row=new Dictionary<string,string>();var physical=info.Records[info.Roots[i]];
     for(int c=0;c<Columns.Count;c++)row[Columns[c]]=c==0?(i+1).ToString():c==3?info.Records[DeclarationRows[i]][3]:physical[c];
     rows.Add(row);
    }
    var meta=new Dictionary<string,object>{{"read_scope","declarations"},{"declaration_rows",names.Count},
     {"accessible_children",Count},{"physical_rows",Rows},{"watch_joined_by_name",true},{"expanded_monitor_rows",Rows-names.Count-2},
     {"declaration_value_source","authenticated_hybrid_frame"},{"live_declaration_rows",names.Count},
     {"complex_initial_source","authenticated_cache_or_physical_root"},{"appended_live_declaration_rows",0},
     {"initializer_origin","per_row_authenticated_compact_or_physical_root_hidden_fields"},
     {"declaration_layout","hybrid_compact_and_physical_roots"},{"physical_root_rows",info.Roots},{"hidden_initializer_rows",DeclarationRows},
     {"stable_two_pass",false},{"atomic_snapshot",false}};
    grid=new Dictionary<string,object>{{"schema",2},{"rows",rows},{"metadata",meta}};
   }
   var keys=new List<int>(hybridCells.Keys);keys.Sort();var cells=new List<object>();var shapes=new List<object>();var seen=new HashSet<int>();
   foreach(int key in keys){int row=key/32,column=key%32;
    cells.Add(new object[]{row,column,29,Columns[column],hybridCells[key]});
    if(seen.Add(row))shapes.Add(new int[]{row,28,Columns.Count});
   }
   if(Source.ChildCount!=Count)throw new Exception("Hybrid frame grid count changed during the actual first pass");
   return new Dictionary<string,object>{{"physical_rows",Rows},{"accessible_children",Count},{"columns",Columns},
    {"observed_cells",cells},{"row_shapes",shapes},{"inventory",inventory},{"grid",grid}};
  }
  public object HybridReadDiagnostics(){return new Dictionary<string,object>{{"observed_cells",hybridCells.Count},
   {"first_pass_value_reads",hybridFirstReads},{"verification_value_reads",hybridVerificationReads},{"same_pass_cache_hits",hybridCacheHits},
   {"scope","same-invocation actual UI first-pass values; every observed field and all full names reread in verification"}};}
  List<int> ReconstructHybrid(List<string> names,List<int> roots,int next){
   if(RequireHybridFrame)throw new Exception("HYBRID_FRAME_REQUIRED: "+OverlapDiagnostic(names,roots,next));
   try{return HybridRoots(names);}
   catch(Exception error){
    string context;try{context=OverlapDiagnostic(names,roots,next);}catch{context="overlap_boundary="+overlapBoundary+"; compact_count="+compactCount+"; physical_rows="+Rows;}
    throw new Exception(error.Message+"; "+context);
   }
  }
  public List<int> WatchRoots(List<string> names){
   List<int> roots=new List<int>();int row=1;
   foreach(string name in names){
    if(row>=Rows || Cell(row,Columns.Count-1)!=name){if(overlapBoundary>=0)return ReconstructHybrid(names,roots,row);throw new Exception("Monitor root/order differs from declaration: "+name);}
    roots.Add(row);row=NextRoot(row,name);
   }
   if(overlapBoundary>=0){
    if(!roots.Contains(overlapBoundary) || row>=Rows || Cell(row,Columns.Count-1)!="")return ReconstructHybrid(names,roots,row);
    CheckOverlapBranches(names,roots);
    overlapRoots=new List<int>(roots);
   }
   // After an edit the compact declaration cache may stop at its old spare
   // row. Only complete, new roots at the end of the monitor preorder
   // can supplement it. Never infer declarations from expanded members.
   var unique=new HashSet<string>(names,StringComparer.OrdinalIgnoreCase);
   var ids=new HashSet<int>();
   bool extra=row<Rows && Cell(row,Columns.Count-1)!="";
   if(extra){
    foreach(int root in roots){
     int id;
     if(!int.TryParse(Cell(root,11),out id) || id<=0 || !ids.Add(id))throw new Exception("Invalid/duplicate live declaration ID");
    }
   }
   while(row<Rows && Cell(row,Columns.Count-1)!=""){
    string name=Cell(row,Key),full=Cell(row,Columns.Count-1),type=Cell(row,2),initial=Cell(row,3);
    int id,number;
    bool stringType=type=="STRING" || Regex.IsMatch(type,@"^STRING<[1-9][0-9]*>$");
    bool scalar=PlainScalar(type) || stringType;
    // Numeric/STRING ARRAY roots expose an empty hidden initializer and an ellipsis.
    // Only canonical one/two-dimensional text qualifies; root identity,
    // branch order, IDs and boundaries are still proved below.
    bool arrayType=Regex.IsMatch(type,@"\A(BOOL|INT|DINT|REAL|BYTE|IP|STRING(<[1-9][0-9]*>)?)\[[1-9][0-9]*(,[1-9][0-9]*)?\]\z");
    var namedArray=Regex.Match(type,@"\A([\p{L}\p{Nl}_][\p{L}\p{Nl}\p{Nd}\p{Mn}\p{Mc}\p{Pc}\p{Cf}]*)\[[1-9][0-9]*(,[1-9][0-9]*)?\]\z");
    bool structureArray=namedArray.Success && !Regex.IsMatch(namedArray.Groups[1].Value,@"\A(BOOL|INT|DINT|REAL|STRING|BYTE|IP|ARRAY)\z",RegexOptions.IgnoreCase);
    bool complex=!scalar && Cell(row,4)=="..." &&
     (Regex.IsMatch(type,@"^[A-Za-z_][A-Za-z0-9_]*$") || (arrayType && initial=="") || structureArray);
    // REAL/BYTE/IP initializers remain exact, bounded source strings. This reader
    // proves complete declaration identity and hidden/display agreement; the
    // IDE/compiler, rather than a second numeric parser, owns semantics.
    bool explicitInitial=initial.Length<=4096 && !Regex.IsMatch(initial,@"[\x00-\x1f]");
    bool validInitial=stringType?(initial.Length<=4096 && Cell(row,4).Length<=4096):
     type=="BOOL"?(initial=="OFF" || initial=="ON"):
     (type=="REAL" || type=="BYTE" || type=="IP")?explicitInitial:
     int.TryParse(initial,out number) && (type!="INT" || (number>=short.MinValue && number<=short.MaxValue));
    if(names.Count>=4096 || name=="" || name.IndexOfAny(new char[]{'.','[',']'})>=0 || full!=name || !unique.Add(name) ||
     Cell(row,0)!=row.ToString() || (!complex && (!scalar || !validInitial || (!stringType && Cell(row,4)!=initial))) ||
     !Regex.IsMatch(Cell(row,10),@"^nBitLen:[1-9][0-9]*$") ||
     (Cell(row,5)!="不保持" && Cell(row,5)!="保持") || (Cell(row,6)!="私有" && Cell(row,6)!="公开") ||
     !int.TryParse(Cell(row,11),out id) || id<=0 || !ids.Add(id))throw new Exception("Incomplete/invalid appended live declaration");
    string[] snapshot=new string[Columns.Count];
    for(int c=0;c<Columns.Count;c++)snapshot[c]=Cell(row,c);
    appended.Add(row,snapshot);DeclarationRows.Add(row);names.Add(name);roots.Add(row);
    if(structureArray)AppendedNamedArrayRoots.Add(name);
    row=NextRoot(row,name);
   }
   if(row>=Rows)throw new Exception("Missing monitor boundary");
   for(int c=Left;c<Columns.Count;c++)if(Cell(row,c)!="")throw new Exception("Unexpected data at monitor boundary");
   // The observed control has exactly one final spare monitor row. Refuse a
   // different layout instead of silently ignoring later declarations/roots.
   if(row!=Rows-1)throw new Exception("Unexpected monitor tail");
   if(appended.Count>0 || overlapBoundary>=0)Blank(row);
   return roots;
  }
  public void Stable(List<string> names){
   if(Hybrid){StableHybrid();return;}
   if(Source.ChildCount!=Count)throw new Exception("Grid size changed during read");
   for(int i=0;i<names.Count;i++)if(Cell(DeclarationRows[i],Key)!=names[i])throw new Exception("Declaration changed during read");
   if(overlapBoundary<0)Blank(compactCount+1);
   else{
    for(int c=0;c<Columns.Count;c++)if(Cell(overlapBoundary,c)!=overlapSnapshot[c])throw new Exception("Overlapping declaration boundary changed during read");
    int row=1;
    for(int i=0;i<names.Count;i++){
     if(row!=overlapRoots[i] || Cell(row,Columns.Count-1)!=names[i])throw new Exception("Monitor root/order changed during read");
     row=NextRoot(row,names[i]);
    }
    if(row!=Rows-1)throw new Exception("Monitor boundary changed during read");
    CheckOverlapBranches(names,overlapRoots);
   }
   foreach(var item in appended)for(int c=0;c<Columns.Count;c++)if(Cell(item.Key,c)!=item.Value[c])throw new Exception("Appended declaration changed during read");
   if(appended.Count>0 || overlapBoundary>=0){Blank(Rows-1);for(int c=Left;c<Columns.Count;c++)if(Cell(Rows-1,c)!="")throw new Exception("Monitor boundary changed during read");}
  }
  public int SpareRow {get{return Hybrid || appended.Count>0 || overlapBoundary>=0?Rows-1:compactCount+1;}}
  public int AppendedCount {get{return appended.Count;}}
  public int LiveRow(int logical,List<string> names,List<int> roots){
   if(!Watch)return logical;
   if(Hybrid)return roots[logical-1];
   int physical=roots[logical-1];string shown=Cell(physical,Key);
   if(shown==names[logical-1])return physical;
   if(shown!="")throw new Exception("Displayed declaration name differs from monitor root");
   for(int c=1;c<Left;c++)if(Cell(physical,c)!="")throw new Exception("Incomplete displayed declaration cache");
   return DeclarationRows[logical-1];
  }
 }

 public static object Read(IBridgeGridSource source){
  return ReadCore(source,false,false);
 }
 public static object ReadInteractive(IBridgeGridSource source){return ReadCore(source,false,true);}
 public static object ReadDisplayed(IBridgeGridSource source){
  return ReadCore(source,true,false);
 }
 public static object ReadRootInventory(IBridgeGridSource source){return new Layout(source).RootInventory();}
 public static object ReadHybridFrame(IBridgeGridSource source){
  Stopwatch timer=Stopwatch.StartNew();object frame=new Layout(source).SingleHybridFrame();
  return new Dictionary<string,object>{{"schema",1},{"profile","autoshop-gvt-hybrid-frame-v1"},
   {"stable_two_pass",false},{"atomic_snapshot",false},{"native_values_used",false},{"frame",frame},{"elapsed_ms",timer.ElapsedMilliseconds}};
 }
 static long JsonStringBudget(string value){
  long count=2;
  for(int i=0;i<value.Length;i++){
   char c=value[i];
   if(c<' ' || c=='\u2028' || c=='\u2029')count+=6;
   else if(c=='"' || c=='\\' || c=='/')count+=2;
   else if(c<128)count++;
   else if(c<2048)count+=2;
   else if(Char.IsHighSurrogate(c) && i+1<value.Length && Char.IsLowSurrogate(value[i+1])){count+=4;i++;}
   else if(Char.IsSurrogate(c))count+=6;
   else count+=3;
  }
  return count;
 }
 public static object ReadDiagnostic(IBridgeGridSource source){
  return DiagnosticRange(source,0,Int32.MaxValue,false);
 }
 public static object ReadDiagnosticPage(IBridgeGridSource source,int offset,int limit){
  if(offset<0 || limit<1 || limit>32)throw new Exception("Raw matrix page requires nonnegative offset and limit 1..32");
  return DiagnosticRange(source,offset,limit,true);
 }
 static object DiagnosticRange(IBridgeGridSource source,int offset,int limit,bool page){
  Layout layout=new Layout(source);
  if(!layout.Watch)throw new Exception("Raw matrix diagnostic requires the observed complete GVT columns");
  if(offset>layout.Rows)throw new Exception("Raw matrix page offset is outside physical rows");
  int end=page?Math.Min(layout.Rows,offset+limit):layout.Rows;
  var rows=new List<string[]>();long budget=2048;
  foreach(string column in layout.Columns)budget+=JsonStringBudget(column)+1;
  var header=new string[layout.Columns.Count];
  for(int column=0;column<header.Length;column++){
   header[column]=layout.Cell(0,column);
   if(header[column]!=layout.Columns[column])throw new Exception("Raw matrix header changed before page read");
   budget+=JsonStringBudget(header[column])+1;
  }
  for(int row=offset;row<end;row++){
   var cells=new string[layout.Columns.Count];budget+=64;
   for(int column=0;column<cells.Length;column++){
    cells[column]=layout.Cell(row,column);budget+=JsonStringBudget(cells[column])+1;
    if(budget>8*1024*1024)throw new Exception("Raw matrix diagnostic complete response exceeds 8 MiB; no fields were truncated");
   }
   rows.Add(cells);
  }
  if(source.ChildCount!=layout.Count)throw new Exception("Raw matrix grid count changed after the complete first pass");
  if(source.Role(layout.Offset)!=28 || source.CellCount(layout.Offset)!=layout.Columns.Count)throw new Exception("Raw matrix header row identity changed during verification");
  for(int column=0;column<layout.Columns.Count;column++)
   if(source.Role(column)!=25 || source.Name(column)!=layout.Columns[column] || layout.Cell(0,column)!=header[column])throw new Exception("Raw matrix column/header identity changed during verification");
  for(int row=offset;row<end;row++){
   int child=layout.Offset+row;
   if(source.Role(child)!=28 || source.CellCount(child)!=layout.Columns.Count)throw new Exception("Raw matrix row/column count changed at row "+row);
   for(int column=0;column<layout.Columns.Count;column++)
    if(layout.Cell(row,column)!=rows[row-offset][column])throw new Exception("Raw matrix value changed at row "+row+", column "+column);
  }
  if(source.ChildCount!=layout.Count)throw new Exception("Raw matrix grid count changed after complete verification");
  return new Dictionary<string,object>{{"schema",1},{"profile",page?"autoshop-gvt-raw-matrix-page-v1":"autoshop-gvt-raw-matrix-v1"},
   {"read_only",true},{"complete",!page},{"complete_page",true},{"stable_two_pass",true},{"atomic_snapshot",false},
   {"columns",layout.Columns},{"header",header},{"raw_rows",rows},{"accessible_children",layout.Count},{"physical_rows",layout.Rows},
   {"offset",offset},{"limit",page?limit:layout.Rows},{"count",rows.Count},{"next_offset",end},{"has_more",end<layout.Rows},
   {"row_index_origin",0},{"includes_header_and_final_boundary",offset==0 && end==layout.Rows},
   {"scope",page?"complete physical cells in this page; aggregate all pages separately":"actual complete physical cells; no declaration inference or native values"},{"response_budget_bytes",budget}};
 }
 static object ReadCore(IBridgeGridSource source,bool displayed,bool requireFrame){
  Stopwatch timer=Stopwatch.StartNew();Layout layout=new Layout(source);
  layout.RequireHybridFrame=requireFrame;
  List<string> names=layout.Declarations();List<int> roots=layout.Watch?layout.WatchRoots(names):null;
  if(!layout.Watch && layout.Rows!=names.Count+2)throw new Exception("Unexpected declaration tail");
  var rows=new List<Dictionary<string,string>>();
  int live=0;
  for(int i=0;i<names.Count;i++){
   int authoritativeRow=layout.DeclarationRows[i],declarationRow=authoritativeRow;
   if(layout.Watch){declarationRow=layout.LiveRow(i+1,names,roots);if(declarationRow==roots[i])live++;}
   var row=new Dictionary<string,string>();
   for(int c=0;c<layout.Columns.Count;c++){
    int sourceRow=layout.Watch && c>=layout.Left?roots[i]:declarationRow;
    if(layout.Watch && c==3 && !displayed){
     string type=layout.Cell(authoritativeRow,2);
     // Complex display previews can materialize nested defaults and comments
     // when a cell is visited. Keep the mapped declaration's hidden value;
     // an appended root has only its actual live hidden field as evidence.
     if(!PlainScalar(type))sourceRow=authoritativeRow;
    }
    row[layout.Columns[c]]=c==0?(i+1).ToString():layout.Cell(sourceRow,c);
   }
   rows.Add(row);
  }
  layout.Stable(names);
  var metadata=new Dictionary<string,object>{{"read_scope","declarations"},{"declaration_rows",names.Count},
   {"accessible_children",layout.Count},{"physical_rows",layout.Rows},{"watch_joined_by_name",layout.Watch},
   {"expanded_monitor_rows",layout.Watch?layout.Rows-names.Count-2:0},{"elapsed_ms",timer.ElapsedMilliseconds},
   {"declaration_value_source",layout.Watch?"name_joined_live_overrides":"compact_rows"},{"live_declaration_rows",live},
   {"complex_initial_source",displayed?"display_preview":(layout.AppendedCount>0?"mapped_declaration_or_appended_live_hidden_field":"compact_declaration")},
   {"appended_live_declaration_rows",layout.AppendedCount},
   {"initializer_origin",layout.AppendedCount>0?"mapped_declaration_cache_or_appended_live_hidden_field":"declaration_cache"}};
  if(layout.AppendedNamedArrayRoots.Count>0){
   metadata["named_array_roots"]=layout.AppendedNamedArrayRoots;
   metadata["named_array_element_qualification"]="syntax_only; native/project qualification is separate";
  }
  if(layout.Hybrid){
   metadata["declaration_layout"]="hybrid_compact_and_physical_roots";
   metadata["physical_root_rows"]=roots;metadata["hidden_initializer_rows"]=displayed?roots:layout.DeclarationRows;
   metadata["complex_initial_source"]=displayed?"display_preview":"authenticated_cache_or_physical_root";
   metadata["initializer_origin"]=displayed?"actual_physical_root_hidden_fields":"per_row_authenticated_compact_or_physical_root_hidden_fields";
   metadata["hybrid_read_diagnostics"]=layout.HybridReadDiagnostics();
  }
  return new Dictionary<string,object>{{"schema",2},{"rows",rows},{"metadata",metadata}};
 }

 public static object ReadInstancePage(IBridgeGridSource source,int offset,int limit){
  if(offset<0 || limit<1 || limit>32)throw new Exception("Invalid FBI page range");
  Layout layout=new Layout(source);List<string> names=layout.Declarations();
  if(layout.Watch || layout.SystemReadOnly || layout.Columns.Count!=11 || layout.Columns[10]!="ID" || layout.Columns[8]!="指针地址")throw new Exception("Expected FBI declaration columns");
  if(layout.Rows!=names.Count+2 || offset>names.Count)throw new Exception("Unexpected FBI declaration boundary/page");
  var rows=new List<Dictionary<string,string>>();
  for(int i=offset;i<Math.Min(names.Count,offset+limit);i++){
   var row=new Dictionary<string,string>();
   for(int c=0;c<layout.Columns.Count;c++)row[layout.Columns[c]]=layout.Cell(layout.DeclarationRows[i],c);
   rows.Add(row);
  }
  layout.Stable(names);
  return new Dictionary<string,object>{{"schema",1},{"scope","fbi_declarations_page"},{"offset",offset},{"limit",limit},
   {"total",names.Count},{"names",names},{"columns",layout.Columns},{"rows",rows}};
 }

 public static CellAddress InstanceSelectionCheckpoint(IBridgeGridSource source,int physicalRows,int physicalRow,string instance,string type,string[] expected,out string[] observed){
  string[] names;return InstanceSelectionCheckpoint(source,physicalRows,physicalRow,instance,type,expected,out observed,out names);
 }
 public static CellAddress InstanceSelectionCheckpoint(IBridgeGridSource source,int physicalRows,int physicalRow,string instance,string type,string[] expected,out string[] observed,out string[] declarationNames){
  Layout layout=new Layout(source);
  if(layout.Watch || layout.SystemReadOnly || layout.Columns.Count!=11 || layout.Columns[8]!="指针地址" || layout.Columns[10]!="ID" ||
   physicalRows!=layout.Rows || physicalRow<1 || physicalRow>=layout.Rows-1 || expected==null || expected.Length!=11 ||
   String.IsNullOrEmpty(instance) || String.IsNullOrEmpty(type))throw new Exception("Physical FBI selection layout/count/row differs");
  List<string> names=layout.Declarations();
  if(layout.Rows!=names.Count+2 || names[physicalRow-1]!=instance)throw new Exception("Physical FBI declaration identity/order differs");
  observed=new string[11];for(int c=0;c<11;c++){
   observed[c]=layout.Cell(physicalRow,c);
   if(expected[c]==null || observed[c]!=expected[c])throw new Exception("Physical FBI complete checkpoint changed at column "+c);
  }
  if(observed[0]!=physicalRow.ToString() || observed[1]!=instance || observed[2]!=type)throw new Exception("Physical FBI full name/type/sequence differs");
  layout.Stable(names);
  declarationNames=names.ToArray();
  return new CellAddress{Child=layout.Offset+physicalRow,DisplayChild=layout.Offset+physicalRow,Column=1,KeyColumn=1,FullNameColumn=-1};
 }

 public static CellAddress PhysicalRoot(IBridgeGridSource source,int physicalRows,int physicalRow,string[] expected,string beforeFull,string afterFull,bool verifyPreorder,out string[] observed){
  Layout layout=new Layout(source);
  if(!layout.Watch || physicalRows!=layout.Rows || physicalRow<1 || physicalRow>=layout.Rows-1 || expected==null || expected.Length!=layout.Columns.Count)
   throw new Exception("Physical root checkpoint count/row/complete columns differ");
  string name=expected[17]??"";
  if(name=="" || name.IndexOfAny(new char[]{'.','[',']'})>=0)throw new Exception("Expected a full top-level monitor root name");
  if(layout.Cell(physicalRow-1,17)!=(beforeFull??"") || layout.Cell(physicalRow+1,17)!=(afterFull??"")
      || (beforeFull??"")==name || (beforeFull??"").StartsWith(name+"[",StringComparison.Ordinal) || (beforeFull??"").StartsWith(name+".",StringComparison.Ordinal))
   throw new Exception("Physical root neighbouring branch checkpoint changed");
  observed=new string[layout.Columns.Count];
  for(int c=0;c<observed.Length;c++){
   observed[c]=layout.Cell(physicalRow,c);
   if(!String.IsNullOrEmpty(expected[c]) && observed[c]!=expected[c])throw new Exception("Physical root nonempty field changed at column "+c);
  }
  if(observed[17]!=name || (observed[1]!="" && observed[1]!=name))throw new Exception("Physical root full/name identity differs");
  if(observed[0]!="" && observed[0]!=physicalRow.ToString())throw new Exception("Physical root sequence differs from its exact row checkpoint");
  int id;
  if(observed[11]!="" && (!Int32.TryParse(observed[11],out id) || id<=0))throw new Exception("Physical root actual ID is invalid");
  if(observed[10]!="" && !Regex.IsMatch(observed[10],@"\AnBitLen:[1-9][0-9]*\z"))throw new Exception("Physical root actual bit-length text is invalid");
  if(verifyPreorder){
   var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);var ids=new HashSet<int>();int row=1;bool found=false;
   while(row<layout.Rows-1){
    string full=layout.Cell(row,17),value=layout.Cell(row,11);
    if(full=="" || full.IndexOfAny(new char[]{'.','[',']'})>=0 || !names.Add(full))throw new Exception("Physical monitor root order/name is incomplete or duplicated");
    if(value!="" && (!Int32.TryParse(value,out id) || id<=0 || !ids.Add(id)))throw new Exception("Physical monitor root ID is invalid or duplicated");
    if(full==name){if(row!=physicalRow)throw new Exception("Physical root moved from its exact checkpoint");found=true;}
    row=layout.NextRoot(row,full);
   }
   if(!found || row!=layout.Rows-1)throw new Exception("Physical root preorder or final boundary differs");
   layout.Blank(row);for(int c=layout.Left;c<layout.Columns.Count;c++)if(layout.Cell(row,c)!="")throw new Exception("Physical root final monitor boundary differs");
  }
  if(source.ChildCount!=layout.Count)throw new Exception("Physical root grid count changed during proof");
  return new CellAddress{Child=layout.Offset+physicalRow,DisplayChild=layout.Offset+physicalRow,Column=layout.Key,KeyColumn=layout.Key,FullNameColumn=17};
 }

 public static CellAddress CellCheckpoint(IBridgeGridSource source,int physicalRows,int sourceRow,int displayRow,int column,string[] sourceExpected,string[] displayExpected,string beforeFull,string afterFull,string variable,string expected,bool spare,out string[] sourceObserved,out string[] displayObserved){
  Layout layout=new Layout(source);
  if(!layout.Watch || physicalRows!=layout.Rows || sourceExpected==null || displayExpected==null || sourceExpected.Length!=18 || displayExpected.Length!=18 || column<1 || column>=layout.Left || sourceRow<1 || sourceRow>=layout.Rows || displayRow<1 || displayRow>=layout.Rows)
   throw new Exception("Cell checkpoint columns/count/physical bounds differ");
  sourceObserved=new string[18];displayObserved=new string[18];
  for(int c=0;c<18;c++){
   sourceObserved[c]=layout.Cell(sourceRow,c);
   displayObserved[c]=sourceRow==displayRow?sourceObserved[c]:layout.Cell(displayRow,c);
   if(sourceExpected[c]==null || displayExpected[c]==null || sourceObserved[c]!=sourceExpected[c] || displayObserved[c]!=displayExpected[c])
    throw new Exception("Cell checkpoint actual field differs at column "+c);
  }
  if(sourceObserved[column]!=expected)throw new Exception("Cell checkpoint requested baseline value differs");
  if(spare){
   int logical;
   if(sourceRow!=displayRow || displayRow!=layout.Rows-1 || !variable.StartsWith("#row:",StringComparison.Ordinal) || !Int32.TryParse(variable.Substring(5),out logical) || logical<1)
    throw new Exception("Cell checkpoint spare identity differs");
   if(displayObserved[0]!="" && displayObserved[0]!=displayRow.ToString())throw new Exception("Cell checkpoint spare sequence differs");
   for(int c=1;c<18;c++)if(displayObserved[c]!="")throw new Exception("Cell checkpoint spare is not completely blank");
   if(afterFull!="")throw new Exception("Cell checkpoint spare after-boundary differs");
  }else{
   if(displayRow>=layout.Rows-1 || variable=="" || variable.IndexOfAny(new char[]{'.','[',']','\r','\n','\0'})>=0 || displayObserved[1]!=variable || displayObserved[17]!=variable || displayObserved[0]!=displayRow.ToString())
    throw new Exception("Cell checkpoint physical root identity differs");
   int id;
   if(!Int32.TryParse(displayObserved[11],out id) || id<=0 || !Regex.IsMatch(displayObserved[10],@"\AnBitLen:[1-9][0-9]*\z"))throw new Exception("Cell checkpoint physical root ID/length differs");
   if(sourceRow!=displayRow){
    if(column!=3 || sourceRow>=layout.Rows-1)throw new Exception("Cell checkpoint distinct source only applies to authenticated hidden initializer");
    foreach(int c in new int[]{1,2,5,6,7})if(sourceObserved[c]!=displayObserved[c])throw new Exception("Cell checkpoint cache/root identity field differs");
    if(sourceObserved[11]!="" && sourceObserved[11]!=displayObserved[11])throw new Exception("Cell checkpoint cache/root ID differs");
   }
   if(beforeFull==variable || (beforeFull??"").StartsWith(variable+"[",StringComparison.Ordinal) || (beforeFull??"").StartsWith(variable+".",StringComparison.Ordinal))throw new Exception("Cell checkpoint target is not a top-level root");
   if(layout.Cell(displayRow+1,17)!=(afterFull??""))throw new Exception("Cell checkpoint following branch differs");
  }
  if(layout.Cell(displayRow-1,17)!=(beforeFull??""))throw new Exception("Cell checkpoint preceding branch differs");
  if(source.ChildCount!=layout.Count)throw new Exception("Cell checkpoint grid count changed");
  return new CellAddress{Child=layout.Offset+sourceRow,DisplayChild=layout.Offset+displayRow,Column=column,KeyColumn=layout.Key,FullNameColumn=17};
 }

 public static CellAddress Find(IBridgeGridSource source,string variable,string column,string expected){
  Layout layout=new Layout(source);List<string> names=layout.Declarations();
  List<int> roots=layout.Watch?layout.WatchRoots(names):null;int c=layout.Columns.IndexOf(column);
  if(layout.SystemReadOnly)throw new Exception("System variable tables are read-only");
  if(c<0)throw new Exception("Unknown grid column");
  int row;
  if(variable.StartsWith("#row:",StringComparison.Ordinal)){
   if(!int.TryParse(variable.Substring(5),out row) || row!=names.Count+1 || c>=layout.Left)throw new Exception("Invalid spare declaration row");
   row=layout.SpareRow;layout.Blank(row);
  }else{
   row=names.IndexOf(variable)+1;
   if(row<1)throw new Exception("Expected one exact declaration name");
   if(layout.Watch && c>=layout.Left)row=roots[row-1];
  }
  int displayRow=row;List<int> displayRoots=null;
  if(layout.Watch && c<layout.Left){
   // MSAA values in the declaration half use compact logical rows. Actual
   // cell geometry/selection uses the expanded monitor's physical rows.
   displayRoots=roots;
   displayRow=variable.StartsWith("#row:",StringComparison.Ordinal)?layout.Rows-1:displayRoots[row-1];
   if(!variable.StartsWith("#row:",StringComparison.Ordinal)){
    int logical=row;row=layout.LiveRow(row,names,displayRoots);
    if(layout.Hybrid && c==3)row=layout.DeclarationRows[logical-1];
   }
  }
  if(layout.Cell(row,c)!=expected)throw new Exception("Cell baseline/identity mismatch");
  layout.Stable(names);
  return new CellAddress{Child=layout.Offset+row,Column=c,DisplayChild=layout.Offset+displayRow,
   KeyColumn=layout.Key,FullNameColumn=layout.Watch?layout.Columns.Count-1:-1};
 }
}
