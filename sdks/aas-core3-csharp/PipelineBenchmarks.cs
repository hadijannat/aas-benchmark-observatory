using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;
using Aas = AasCore.Aas3_0;

namespace AasBenchmark;

[MemoryDiagnoser]
public class PipelineBenchmarks
{
    [ParamsSource(nameof(AvailableDatasets))]
    public string Dataset { get; set; } = "mixed";

    public static IEnumerable<string> AvailableDatasets()
    {
        var dir = Environment.GetEnvironmentVariable("DATASETS_DIR") ?? "";
        if (Directory.Exists(dir))
        {
            return Directory.GetFiles(dir, "*.json")
                .Select(f => Path.GetFileNameWithoutExtension(f))
                .OrderBy(n => n);
        }
        return new[] { "wide", "deep", "mixed" };
    }

    private string _rawJson = string.Empty;
    private JsonNode? _jsonNode;
    private Aas.IEnvironment? _env;

    [GlobalSetup]
    public void Setup()
    {
        var datasetsDir = Environment.GetEnvironmentVariable("DATASETS_DIR");
        if (string.IsNullOrEmpty(datasetsDir))
        {
            throw new InvalidOperationException("DATASETS_DIR environment variable not set");
        }

        var filePath = Path.Combine(datasetsDir, $"{Dataset}.json");
        _rawJson = File.ReadAllText(filePath);
        _jsonNode = JsonNode.Parse(_rawJson);
        _env = Aas.Jsonization.Deserialize.EnvironmentFrom(_jsonNode!);
    }

    [Benchmark]
    public Aas.IEnvironment Deserialize()
    {
        var node = JsonNode.Parse(_rawJson)!;
        return Aas.Jsonization.Deserialize.EnvironmentFrom(node);
    }

    [Benchmark]
    public List<string> Validate()
    {
        var errors = new List<string>();
        foreach (var error in Aas.Verification.Verify(_env!))
        {
            errors.Add(error.Cause.ToString());
        }
        return errors;
    }

    [Benchmark]
    public int Traverse()
    {
        int count = 0;
        foreach (var _ in _env!.Descend())
        {
            count++;
        }
        return count;
    }

    [Benchmark]
    public int Update()
    {
        int count = 0;
        foreach (var node in _env!.Descend())
        {
            if (node is Aas.IProperty prop && prop.Value != null)
            {
                prop.Value = prop.Value + "_updated";
                count++;
            }
        }
        return count;
    }

    [Benchmark]
    public string Serialize()
    {
        var jsonObject = Aas.Jsonization.Serialize.ToJsonObject(_env!);
        return jsonObject.ToJsonString();
    }
}

public class Program
{
    public static void Main(string[] args)
    {
        BenchmarkSwitcher.FromAssembly(typeof(Program).Assembly).Run(args);
    }
}
