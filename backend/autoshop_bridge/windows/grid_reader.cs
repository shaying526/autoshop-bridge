// Pure declaration/monitor layout reader, also exercised with an in-memory source.
using System;
using System.Collections.Generic;
using System.Diagnostics;

public interface IBridgeGridSource {
 int ChildCount {get;}
 int Role(int child);
 string Name(int child);
 int CellCount(int child);
 int CellRole(int child,int column);
 string CellName(int child,int column);
 string Value(int child,int column);
}

public static class BridgeGridReader {
 public sealed class CellAddress {public int Child;public int Column;public int DisplayChild;public int KeyColumn;public int FullNameColumn;}
 sealed class Layout {
  public IBridgeGridSource Source;public int Count,Offset,Rows,Key,Left;
  public bool Watch;public List<string> Columns=new List<string>();
  public bool SystemReadOnly;
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
    if(name==""){Blank(row);return names;}
    if(row>4096 || Cell(row,0)!=row.ToString() || !unique.Add(name))throw new Exception("Invalid/duplicate declaration row");
    names.Add(name);
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
  public List<int> WatchRoots(List<string> names){
   List<int> roots=new List<int>();int row=1;
   foreach(string name in names){
    if(row>=Rows || Cell(row,Columns.Count-1)!=name)throw new Exception("Monitor root/order differs from declaration: "+name);
    roots.Add(row);row=NextRoot(row,name);
   }
   if(row>=Rows)throw new Exception("Missing monitor boundary");
   for(int c=Left;c<Columns.Count;c++)if(Cell(row,c)!="")throw new Exception("Unexpected data at monitor boundary");
   // The observed control has exactly one final spare monitor row. Refuse a
   // different layout instead of silently ignoring later declarations/roots.
   if(row!=Rows-1)throw new Exception("Unexpected monitor tail");
   return roots;
  }
  public void Stable(List<string> names){
   if(Source.ChildCount!=Count)throw new Exception("Grid size changed during read");
   for(int i=0;i<names.Count;i++)if(Cell(i+1,Key)!=names[i])throw new Exception("Declaration changed during read");
   Blank(names.Count+1);
  }
  public int LiveRow(int logical,List<string> names,List<int> roots){
   if(!Watch)return logical;
   int physical=roots[logical-1];string shown=Cell(physical,Key);
   if(shown==names[logical-1])return physical;
   if(shown!="")throw new Exception("Displayed declaration name differs from monitor root");
   for(int c=1;c<Left;c++)if(Cell(physical,c)!="")throw new Exception("Incomplete displayed declaration cache");
   return logical;
  }
 }

 public static object Read(IBridgeGridSource source){
  return ReadCore(source,false);
 }
 public static object ReadDisplayed(IBridgeGridSource source){
  return ReadCore(source,true);
 }
 static object ReadCore(IBridgeGridSource source,bool displayed){
  Stopwatch timer=Stopwatch.StartNew();Layout layout=new Layout(source);
  List<string> names=layout.Declarations();List<int> roots=layout.Watch?layout.WatchRoots(names):null;
  if(!layout.Watch && layout.Rows!=names.Count+2)throw new Exception("Unexpected declaration tail");
  var rows=new List<Dictionary<string,string>>();
  int live=0;
  for(int i=0;i<names.Count;i++){
   int declarationRow=i+1;
   if(layout.Watch){declarationRow=layout.LiveRow(i+1,names,roots);if(declarationRow==roots[i])live++;}
   var row=new Dictionary<string,string>();
   for(int c=0;c<layout.Columns.Count;c++){
    int sourceRow=layout.Watch && c>=layout.Left?roots[i]:(c==0?i+1:declarationRow);
    if(layout.Watch && c==3 && !displayed){
     string type=layout.Cell(i+1,2);
     // Complex display previews can materialize nested defaults and comments
     // when a cell is visited. Keep the explicit declaration's hidden value.
     if(type!="BOOL" && type!="INT" && type!="DINT" && type!="REAL")sourceRow=i+1;
    }
    row[layout.Columns[c]]=layout.Cell(sourceRow,c);
   }
   rows.Add(row);
  }
  layout.Stable(names);
  var metadata=new Dictionary<string,object>{{"read_scope","declarations"},{"declaration_rows",names.Count},
   {"accessible_children",layout.Count},{"physical_rows",layout.Rows},{"watch_joined_by_name",layout.Watch},
   {"expanded_monitor_rows",layout.Watch?layout.Rows-names.Count-2:0},{"elapsed_ms",timer.ElapsedMilliseconds},
   {"declaration_value_source",layout.Watch?"name_joined_live_overrides":"compact_rows"},{"live_declaration_rows",live},
   {"complex_initial_source",displayed?"display_preview":"compact_declaration"}};
  return new Dictionary<string,object>{{"schema",2},{"rows",rows},{"metadata",metadata}};
 }

 public static CellAddress Find(IBridgeGridSource source,string variable,string column,string expected){
  Layout layout=new Layout(source);List<string> names=layout.Declarations();int c=layout.Columns.IndexOf(column);
  if(layout.SystemReadOnly)throw new Exception("System variable tables are read-only");
  if(c<0)throw new Exception("Unknown grid column");
  int row;
  if(variable.StartsWith("#row:",StringComparison.Ordinal)){
   if(!int.TryParse(variable.Substring(5),out row) || row!=names.Count+1 || c>=layout.Left)throw new Exception("Invalid spare declaration row");
   layout.Blank(row);
  }else{
   row=names.IndexOf(variable)+1;
   if(row<1)throw new Exception("Expected one exact declaration name");
   if(layout.Watch && c>=layout.Left)row=layout.WatchRoots(names)[row-1];
  }
  int displayRow=row;List<int> displayRoots=null;
  if(layout.Watch && c<layout.Left){
   // MSAA values in the declaration half use compact logical rows. Actual
   // cell geometry/selection uses the expanded monitor's physical rows.
   displayRoots=layout.WatchRoots(names);
   displayRow=variable.StartsWith("#row:",StringComparison.Ordinal)?layout.Rows-1:displayRoots[row-1];
   if(!variable.StartsWith("#row:",StringComparison.Ordinal))row=layout.LiveRow(row,names,displayRoots);
  }
  if(layout.Cell(row,c)!=expected)throw new Exception("Cell baseline/identity mismatch");
  layout.Stable(names);
  return new CellAddress{Child=layout.Offset+row,Column=c,DisplayChild=layout.Offset+displayRow,
   KeyColumn=layout.Key,FullNameColumn=layout.Watch?layout.Columns.Count-1:-1};
 }
}
