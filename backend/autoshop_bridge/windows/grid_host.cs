// Fixed read-only entry point. Never handles selection, edits or persistence.
using System;
using System.Collections.Generic;
using System.Text;
using System.Web.Script.Serialization;

public static class BridgeGridHost {
 [STAThread]
 public static int Main(string[] args) {
  Console.OutputEncoding=new UTF8Encoding(false);
  var json=new JavaScriptSerializer();json.MaxJsonLength=8*1024*1024;
  try {
   if(args.Length!=1 || args[0].Length>65536)throw new Exception("Invalid grid host request size");
   var r=json.Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(Convert.FromBase64String(args[0])));
   if(r==null || r.Count!=7 || !(r["protocol"] is int) || (int)r["protocol"]!=1 || (string)r["action"]!="grid")throw new Exception("Unsupported grid host request");
   if(!(r["project"] is string) || !(r["program"] is string) || ((string)r["project"]).Length>8192 || ((string)r["program"]).Length>1024)throw new Exception("Invalid grid host identity");
   object result=BridgeAccessibility.Run("grid",Convert.ToInt64(r["main"]),Convert.ToInt64(r["target"]),Convert.ToInt32(r["pid"]),(string)r["project"],(string)r["program"],null,null,null);
   string output=json.Serialize(new Dictionary<string,object>{{"status","ok"},{"result",result}});
   if(output.Length>8*1024*1024)throw new Exception("Grid host response exceeds limit");
   Console.WriteLine(output);return 0;
  } catch(Exception e) {
   Console.WriteLine(json.Serialize(new Dictionary<string,object>{{"status","error"},{"error",e.Message}}));return 1;
  }
 }
}
