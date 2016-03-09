
import requests


BASE_URL = "http://localhost:8000/xhr/units/"
PATHS_FILE = "paths.txt"

PARAMS = [
    "filter=all",
    "filter=all&sort=oldest",
    "filter=incomplete&sort=oldest",
    "filter=untranslated&sort=oldest",
    "filter=all&sort=newest",
    "filter=incomplete&sort=newest",
    "filter=translated&sort=newest",
    "filter=untranslated&sort=newest",
    "filter=untranslated&sort=oldest"]


class MarkdownTableFormatter(object):

    def __init__(self, num_of_results=50, include_sql=False):
        self.num_of_results = num_of_results
        self.include_sql = include_sql

    def format(self, performance_test):
        data = performance_test.results
        results = list(
            reversed(
                sorted(
                    data,
                    key=lambda res: res[1])))[:20]
        path_width = max(max(len(x[0]) for x in results), 10)
        timing_width = max(max(len(str(x[1])) for x in results), 10)

        total = sum(x[1] for x in data)

        if self.include_sql:
            sql_width = max(max(len(x[2]) for x in results), 10)

        if self.include_sql:
            print(
                "|path%s|timing%s|sql%s|"
                % ((" " * (path_width - 4)),
                   (" " * (timing_width - 6)),
                   (" " * (sql_width - 3))))
        else:
            print(
                "|path%s|timing%s|"
                % ((" " * (path_width - 4)),
                   (" " * (timing_width - 6))))

        if self.include_sql:
            print(
                "|%s|%s|%s|"
                % ("-" * path_width,
                   "-" * timing_width,
                   "-" * sql_width))
        else:
            print(
                "|%s|%s|"
                % ("-" * path_width,
                   "-" * timing_width))

        for path, timing, sql in results:
            if self.include_sql:
                print (
                    "|%s%s|%s%s|%s%s|"
                    % (path, (" " * (path_width - len(path))),
                       timing, (" " * (timing_width - len(str(timing)))),
                       sql, (" " * (sql_width - len(sql)))))
            else:
                print (
                    "|%s%s|%s%s|"
                    % (path, (" " * (path_width - len(path))),
                       timing, (" " * (timing_width - len(str(timing))))))

        if self.include_sql:
            print(
                "|%s|%s|%s|"
                % ("-" * path_width,
                   "-" * timing_width,
                   "-" * sql_width))
        else:
            print(
                "|%s|%s|"
                % ("-" * path_width,
                   "-" * timing_width))

        if self.include_sql:
            print(
                "|total%s|%s|%s%s|"
                % ((" " * (path_width - 5)),
                   (" " * (timing_width)),
                   total,
                   (" " * (sql_width - len(str(total))))))
        else:
            print(
                "|total%s|%s%s|"
                % ((" " * (path_width - 5)),
                   total,
                   (" " * (timing_width - len(str(total))))))


class GetUnitsPerformance(object):

    def __init__(self, base_url=BASE_URL, paths_file=PATHS_FILE):
        self.base_url = base_url
        self.paths_file = paths_file

    def get_paths(self):
        with open(self.paths_file, "r") as f:
            for line in f.readlines():
                yield line.strip()

    def get_params(self):
        return PARAMS

    @property
    def results(self):
        result = []

        for path in self.get_paths():
            for param in self.get_params():
                url = (
                    "%s?path=%s&initial=true&%s"
                    % (self.base_url, path, param))
                resp = requests.get(url)
                if not path.endswith("/"):
                    timing = sum(
                        float(t["time"])
                        for t
                        in resp.json()["queries"][-2:])
                else:
                    timing = float(resp.json()["queries"][-1]["time"])
                sql = resp.json()["queries"][-1]["sql"]
                result.append(
                    (url.split("?")[1], timing, sql))
        return result


def run():
    MarkdownTableFormatter().format(GetUnitsPerformance())

if __name__ == "__main__":
    run()
