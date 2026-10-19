"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadFilterFunctions() {
  const appPath = path.join(__dirname, "..", "institution_catalog", "workbench", "static", "app.js");
  const source = fs.readFileSync(appPath, "utf8").replace(/initialize\(\);\s*$/, "");
  const context = vm.createContext({ console });
  vm.runInContext(source, context, { filename: appPath });
  return context;
}

function record(organizationSystem, institutionType) {
  return {
    deleted: false,
    data: {
      organization_system: organizationSystem,
      institution_type: institutionType,
    },
  };
}

function main() {
  const context = loadFilterFunctions();
  context.testRecords = [
    record("央企", "财政部金融央企"),
    record("中共中央", "中央领导"),
    record("新增组织体系", "新增类型"),
    record("群团组织", "其他群团组织"),
    record("民主党派", "八大民主党派"),
    record("央企", "财政部行政央企"),
    record("中共中央", "中央机构"),
    record("央企", "财政部文化央企"),
  ];
  vm.runInContext("appState.records = testRecords", context);

  const systems = vm.runInContext("organizationSystemValues()", context);
  assert.deepEqual(Array.from(systems), [
    "央企",
    "中共中央",
    "新增组织体系",
    "群团组织",
    "民主党派",
  ]);

  const types = vm.runInContext(
    'uniqueValuesInAppearanceOrder("institution_type", recordsInOrganizationSystemOrder(appState.records))',
    context,
  );
  assert.deepEqual(Array.from(types), [
    "财政部金融央企",
    "中央领导",
    "新增类型",
    "其他群团组织",
    "八大民主党派",
    "财政部行政央企",
    "中央机构",
    "财政部文化央企",
  ]);

  vm.runInContext(`
    appState.fields = [
      { field_id: "organization_system", export_name: "组织体系" },
      { field_id: "institution_name", export_name: "机构名称" },
      { field_id: "official_url", export_name: "官网链接", is_link: true },
    ];
    appState.hiddenFieldIds = new Set(["official_url"]);
    appState.filtered = [
      { data: { organization_system: "央企", institution_name: "甲\\t机构", official_url: "https://example.com" } },
      { data: { organization_system: "群团组织", institution_name: "乙\\n机构", official_url: "" } },
    ];
  `, context);
  const visibleNames = vm.runInContext("visibleFields().map((field) => field.export_name).join(',')", context);
  assert.equal(visibleNames, "组织体系,机构名称");
  const copiedTable = vm.runInContext("buildVisibleTableText()", context);
  assert.equal(copiedTable, "组织体系\t机构名称\r\n央企\t甲 机构\r\n群团组织\t乙 机构");

  const virtualTop = vm.runInContext("calculateVirtualWindow(7768, 0, 16)", context);
  assert.deepEqual({ ...virtualTop }, { start: 0, end: 100 });
  const virtualMiddle = vm.runInContext("calculateVirtualWindow(7768, 4000, 16)", context);
  assert.equal(virtualMiddle.end - virtualMiddle.start, 100);
  assert.ok(virtualMiddle.start < 4000 && virtualMiddle.end > 4015);
  const virtualBottom = vm.runInContext("calculateVirtualWindow(7768, 7760, 16)", context);
  assert.deepEqual({ ...virtualBottom }, { start: 7668, end: 7768 });
  const virtualShort = vm.runInContext("calculateVirtualWindow(42, 20, 16)", context);
  assert.deepEqual({ ...virtualShort }, { start: 0, end: 42 });

  console.log("筛选项排序、可见表格复制与虚拟窗口测试通过");
}

main();
