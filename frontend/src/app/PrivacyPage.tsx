import { Link } from 'react-router-dom';

export function PrivacyPage() {
  return (
    <main className="privacy-page">
      <article className="privacy-document">
        <Link className="privacy-back" to="/tasks">
          返回工作台
        </Link>
        <h1>外部 AI 数据处理说明</h1>
        <p>
          文档正文、任务指令和必要上下文仅在用户主动提交需要模型判断的任务时，
          发送给配置的外部 AI 服务。
        </p>
        <p>
          本地文件操作、格式解析、验证和不需要模型参与的转换仍在本机执行。
          应用不会把完整文档长期保存在外部服务中。
        </p>
        <p>
          任务记录、上传文件和结果文件保存在本机数据目录，并由本地路径守卫限制访问。
        </p>
      </article>
    </main>
  );
}
